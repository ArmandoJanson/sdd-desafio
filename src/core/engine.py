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
_Avaliacao = Tuple[str, Decimal, str]  # status, valor reembolsado, justificativa


class CompetenciaInvalidaError(ValueError):
    """Competência fora de ``YYYY-MM`` (RN-009): o arquivo é recusado."""


def _rejeitar(justificativa: str) -> _Avaliacao:
    return rules.STATUS_REJEITADO, ZERO, justificativa


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
            avaliacoes[posicao] = _rejeitar(rules.JUSTIFICATIVA_VALOR)
        elif not rules.categoria_permitida(despesa.categoria):
            avaliacoes[posicao] = (
                rules.STATUS_CATEGORIA_INVALIDA,
                ZERO,
                rules.JUSTIFICATIVA_CATEGORIA,
            )

    # 3. RN-007: entre as que seguem na esteira, vale a duplicata mais recente.
    vivas = [p for p in range(len(despesas)) if p not in avaliacoes]
    for indice in rules.posicoes_duplicadas([despesas[p] for p in vivas]):
        avaliacoes[vivas[indice]] = (
            rules.STATUS_DUPLICIDADE,
            ZERO,
            rules.JUSTIFICATIVA_DUPLICIDADE,
        )

    # 4. RN-006: data dentro da competência.
    for posicao in (p for p in range(len(despesas)) if p not in avaliacoes):
        if not rules.dentro_da_competencia(despesas[posicao].data, solicitacao.periodo):
            avaliacoes[posicao] = _rejeitar(rules.JUSTIFICATIVA_PERIODO)

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
    tetos: Dict[Tuple, Decimal] = {}
    for posicao in vivas:
        despesa = despesas[posicao]
        if posicao in avaliacoes:
            continue
        if despesa.categoria == rules.CATEGORIA_COWORKING:
            avaliacoes[posicao] = (
                rules.STATUS_APROVADO,
                despesa.valor,
                rules.JUSTIFICATIVA_APROVADO,
            )
        elif rules.falta_nota_fiscal(despesa):
            continue
        else:
            chave = (despesa.categoria, despesa.data)
            em_viagem = despesa.data in dias_viagem
            if chave not in restante:
                tetos[chave] = restante[chave] = rules.limite_diario(
                    despesa.categoria, em_viagem
                )
            status, reembolso = rules.aplicar_teto(despesa.valor, restante[chave])
            restante[chave] -= reembolso
            regra = (
                "RN-001"
                if despesa.categoria == rules.CATEGORIA_ALIMENTACAO
                else "RN-002"
            )
            detalhe = "ampliado em 50% por viagem (RN-005)" if em_viagem else ""
            avaliacoes[posicao] = (
                status,
                reembolso,
                rules.justificar_teto(status, tetos[chave], regra, detalhe),
            )

    # 7. RN-004: nota fiscal para despesas acima de R$ 100,00.
    for posicao in vivas:
        if rules.falta_nota_fiscal(despesas[posicao]):
            avaliacoes[posicao] = _rejeitar(rules.JUSTIFICATIVA_NOTA_FISCAL)

    return [avaliacoes[p] for p in range(len(despesas))]


def avaliar(solicitacao: SolicitacaoReembolso) -> ResultadoAuditoria:
    """Aplica a esteira de regras e monta o resultado da auditoria.

    Levanta ``CompetenciaInvalidaError`` se a competência não for ``YYYY-MM``.
    """
    avaliacoes = _avaliar_despesas(solicitacao)
    itens = [
        _item(despesa, *avaliacao)
        for despesa, avaliacao in zip(solicitacao.despesas, avaliacoes)
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


def _item(
    despesa: Despesa, status: str, valor: Decimal, justificativa: str
) -> ItemAuditoria:
    return ItemAuditoria(
        id=despesa.id,
        data=despesa.data,
        descricao=despesa.descricao,
        fornecedor=despesa.fornecedor,
        status_item=status,
        justificativa=justificativa,
        valor_reembolsado=valor,
    )
