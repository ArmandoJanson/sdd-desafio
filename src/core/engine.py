"""Orquestrador do motor de reembolso: esteira da spec.md, seção 8.

Puro: recebe a ``SolicitacaoReembolso`` e devolve o ``ResultadoAuditoria``,
sem tocar em disco ou interface.
"""

from decimal import Decimal
from typing import Dict, List, Tuple

from core import rules
from core.models import (
    ColaboradorResultado,
    Despesa,
    HistoricoCompetencia,
    ItemAuditoria,
    ResultadoAuditoria,
    SolicitacaoReembolso,
)

ZERO = Decimal("0.00")
_Avaliacao = Tuple[str, Decimal]


class CompetenciaInvalidaError(ValueError):
    """Competência fora de ``YYYY-MM`` (RN-009): o arquivo é recusado."""


def _rejeitar() -> _Avaliacao:
    return rules.STATUS_REJEITADO, ZERO


def _avaliar_despesas(solicitacao: SolicitacaoReembolso) -> List[_Avaliacao]:
    """Status e valor reembolsado de cada despesa, na ordem de entrada."""
    despesas = [
        d.model_copy(update={"valor": rules.normalizar_valor(d.valor)})
        for d in solicitacao.despesas
    ]
    avaliacoes: Dict[int, _Avaliacao] = {}

    # RN-009: competência inválida ou nula recusa o arquivo, sem resultado.
    competencia = solicitacao.periodo.competencia
    if not rules.competencia_valida(competencia):
        raise CompetenciaInvalidaError(
            f"competência deve seguir o formato YYYY-MM, recebido: {competencia!r}"
        )

    # 1. RN-010: valores zerados ou negativos.
    # 2. RN-008: categoria exatamente igual a uma das permitidas.
    for posicao, despesa in enumerate(despesas):
        if not rules.valor_elegivel(despesa.valor):
            avaliacoes[posicao] = _rejeitar()
        elif not rules.categoria_permitida(despesa.categoria):
            avaliacoes[posicao] = (rules.STATUS_CATEGORIA_INVALIDA, ZERO)

    # 3. RN-007: entre as que seguem na esteira, vale a duplicata mais recente.
    vivas = [p for p in range(len(despesas)) if p not in avaliacoes]
    for indice in rules.posicoes_duplicadas([despesas[p] for p in vivas]):
        avaliacoes[vivas[indice]] = (rules.STATUS_DUPLICIDADE, ZERO)

    # 4. RN-006: data dentro da competência.
    for posicao in (p for p in range(len(despesas)) if p not in avaliacoes):
        if not rules.dentro_da_competencia(despesas[posicao].data, solicitacao.periodo):
            avaliacoes[posicao] = _rejeitar()

    vivas = [p for p in range(len(despesas)) if p not in avaliacoes]

    # 5. RN-005 / RN-003: contexto de viagem e hospedagem.
    dias_viagem = rules.dias_em_viagem(
        despesas[p] for p in vivas if rules.hospedagem_de_viagem(despesas[p])
    )
    for posicao in vivas:
        if despesas[posicao].categoria == rules.CATEGORIA_HOSPEDAGEM:
            avaliacoes[posicao] = rules.avaliar_hospedagem(despesas[posicao])

    # 6. RN-001 / RN-002: tetos diários, consumidos na ordem de lançamento.
    # Quem será rejeitado por falta de nota fiscal (7) não consome o teto.
    restante: Dict[Tuple, Decimal] = {}
    for posicao in vivas:
        despesa = despesas[posicao]
        if posicao in avaliacoes:
            continue
        if despesa.categoria == rules.CATEGORIA_COWORKING:
            avaliacoes[posicao] = (rules.STATUS_APROVADO, despesa.valor)
        elif rules.falta_nota_fiscal(despesa):
            continue
        else:
            chave = (despesa.categoria, despesa.data)
            if chave not in restante:
                restante[chave] = rules.limite_diario(
                    despesa.categoria, despesa.data in dias_viagem
                )
            avaliacoes[posicao] = rules.aplicar_teto(despesa.valor, restante[chave])
            restante[chave] -= avaliacoes[posicao][1]

    # 7. RN-004: nota fiscal para despesas acima de R$ 100,00.
    for posicao in vivas:
        if rules.falta_nota_fiscal(despesas[posicao]):
            avaliacoes[posicao] = _rejeitar()

    return [avaliacoes[p] for p in range(len(despesas))]


def avaliar(solicitacao: SolicitacaoReembolso) -> ResultadoAuditoria:
    """Aplica a esteira de regras e monta o resultado da auditoria.

    Levanta ``CompetenciaInvalidaError`` se a competência não for ``YYYY-MM``.
    """
    avaliacoes = _avaliar_despesas(solicitacao)
    itens = [
        _item(despesa, status, valor)
        for despesa, (status, valor) in zip(solicitacao.despesas, avaliacoes)
    ]
    colaborador = solicitacao.colaborador
    return ResultadoAuditoria(
        colaborador=ColaboradorResultado(
            id=colaborador.id, centro_custo=colaborador.centro_custo
        ),
        historico_despesas=[
            HistoricoCompetencia(
                competencia=solicitacao.periodo.competencia,
                centro_custo=colaborador.centro_custo,
                despesas=itens,
            )
        ],
    )


def _item(despesa: Despesa, status: str, valor: Decimal) -> ItemAuditoria:
    return ItemAuditoria(
        id=despesa.id,
        data=despesa.data,
        descricao=despesa.descricao,
        fornecedor=despesa.fornecedor,
        status_item=status,
        valor_reembolsado=valor,
    )
