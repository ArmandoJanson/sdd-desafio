"""Regras de negócio do motor de reembolso (spec.md, seção 5).

Funções puras: recebem modelos/valores e devolvem decisões, sem I/O. A ordem
em que são aplicadas (spec.md, seção 8) é responsabilidade de ``engine.py``.
Decisões provisórias de interpretação estão na spec, seção 10.
"""

import re
from datetime import date, timedelta
from decimal import Decimal
from typing import Iterable, Optional, Sequence, Set, Tuple

from core.models import Despesa, Periodo, arredondar_centavos

# --------------------------------------------------------------------------
# Constantes de negócio
# --------------------------------------------------------------------------

STATUS_APROVADO = "aprovado"
STATUS_PARCIAL = "parcial"
STATUS_REJEITADO = "rejeitado"
STATUS_CATEGORIA_INVALIDA = "rejeitado - categoria inválida"
STATUS_DUPLICIDADE = "rejeitado - duplicidade"

# Justificativas fixas (spec.md, seção 4: campo ``justificativa``).
JUSTIFICATIVA_APROVADO = "Despesa aprovada integralmente."
JUSTIFICATIVA_VALOR = "Valor zerado ou negativo não é reembolsável (RN-010)."
JUSTIFICATIVA_CATEGORIA = "Categoria fora da política de reembolso (RN-008)."
JUSTIFICATIVA_DUPLICIDADE = (
    "Duplicata de uma despesa idêntica com id mais recente (RN-007)."
)
JUSTIFICATIVA_PERIODO = "Data da despesa fora do período de competência (RN-006)."
JUSTIFICATIVA_FORNECEDOR_HOSPEDAGEM = (
    "Hospedagem sem fornecedor reconhecido "
    "(hotel, airbnb, pousada, hostel ou camping) (RN-003)."
)
JUSTIFICATIVA_NOTA_FISCAL = (
    "Nota fiscal obrigatória para despesa acima de R$ 100,00 (RN-004)."
)

CATEGORIA_ALIMENTACAO = "alimentacao"
CATEGORIA_COWORKING = "coworking"
CATEGORIA_HOSPEDAGEM = "hospedagem"
CATEGORIA_TRANSPORTE = "transporte_urbano"

CATEGORIAS_PERMITIDAS = (
    CATEGORIA_ALIMENTACAO,
    CATEGORIA_COWORKING,
    CATEGORIA_HOSPEDAGEM,
    CATEGORIA_TRANSPORTE,
)

LIMITES_DIARIOS = {
    CATEGORIA_ALIMENTACAO: Decimal("60.00"),  # RN-001
    CATEGORIA_TRANSPORTE: Decimal("80.00"),  # RN-002
}
LIMITE_HOSPEDAGEM_POR_DIARIA = Decimal("250.00")  # RN-003
FATOR_VIAGEM = Decimal("1.5")  # RN-005: limites ampliados em 50%
LIMITE_SEM_NOTA_FISCAL = Decimal("100.00")  # RN-004: acima disso exige NF
PALAVRAS_VIAGEM = ("hotel", "airbnb", "pousada", "hostel", "camping")

_COMPETENCIA = re.compile(r"[0-9]{4}-(0[1-9]|1[0-2])")
_NUMERO = re.compile(r"[0-9]+")
_PARTES_ID = re.compile(r"([0-9]+)")


# --------------------------------------------------------------------------
# RN-009 / RN-010 / RN-011 — entradas gerais
# --------------------------------------------------------------------------


def competencia_valida(competencia: Optional[str]) -> bool:
    """RN-009: ``YYYY-MM`` com mês entre 01 e 12; vazio ou nulo é inválido."""
    return isinstance(competencia, str) and bool(_COMPETENCIA.fullmatch(competencia))


def valor_elegivel(valor: Decimal) -> bool:
    """RN-010: valores negativos ou zerados não são reembolsáveis."""
    return valor > 0


def normalizar_valor(valor: Decimal) -> Decimal:
    """RN-011: duas casas decimais, arredondamento matemático."""
    return arredondar_centavos(valor)


# --------------------------------------------------------------------------
# RN-008 — categorias
# --------------------------------------------------------------------------


def categoria_permitida(categoria: str) -> bool:
    """RN-008: comparação exata (sem tolerar acento, caixa ou espaço)."""
    return categoria in CATEGORIAS_PERMITIDAS


# --------------------------------------------------------------------------
# RN-007 — duplicatas
# --------------------------------------------------------------------------


def chave_id(id_despesa: str) -> Tuple:
    """Ordem "natural" de ids: trechos numéricos comparados como números."""
    return tuple(
        int(parte) if indice % 2 else parte
        for indice, parte in enumerate(_PARTES_ID.split(id_despesa))
    )


def chave_duplicidade(despesa: Despesa) -> Tuple:
    return (
        despesa.data,
        despesa.categoria,
        despesa.fornecedor,
        despesa.descricao,
        despesa.valor,
    )


def posicoes_duplicadas(despesas: Sequence[Despesa]) -> Set[int]:
    """Posições das despesas antigas em grupos de duplicatas perfeitas.

    Em cada grupo vale a de id mais recente; em empate de id, a lançada por
    último. As demais devem ser rejeitadas.
    """
    vencedora = {}
    for posicao, despesa in enumerate(despesas):
        chave = chave_duplicidade(despesa)
        atual = vencedora.get(chave)
        if atual is None or chave_id(despesa.id) >= chave_id(despesas[atual].id):
            vencedora[chave] = posicao
    mantidas = set(vencedora.values())
    return {posicao for posicao in range(len(despesas)) if posicao not in mantidas}


# --------------------------------------------------------------------------
# RN-006 — período de competência
# --------------------------------------------------------------------------


def dentro_da_competencia(data: date, periodo: Periodo) -> bool:
    """RN-006: ``inicio`` e ``fim`` são inclusivos."""
    return periodo.inicio <= data <= periodo.fim


# --------------------------------------------------------------------------
# RN-005 / RN-003 — viagem e hospedagem
# --------------------------------------------------------------------------


def hospedagem_de_viagem(despesa: Despesa) -> bool:
    """Hospedagem cujo fornecedor contém uma palavra-chave (sem caixa)."""
    if despesa.categoria != CATEGORIA_HOSPEDAGEM:
        return False
    fornecedor = despesa.fornecedor.lower()
    return any(palavra in fornecedor for palavra in PALAVRAS_VIAGEM)


def numero_de_diarias(descricao: str) -> int:
    """Primeiro número inteiro da descrição; sem número (ou zero), 1."""
    achado = _NUMERO.search(descricao)
    return max(int(achado.group()), 1) if achado else 1


def dias_de_viagem(descricao: str) -> int:
    """Dias cobertos pela viagem: N para diárias, N + 1 para noites."""
    quantidade = numero_de_diarias(descricao)
    informou_numero = _NUMERO.search(descricao) is not None
    if informou_numero and "noite" in descricao.lower():
        return quantidade + 1
    return quantidade


def dias_em_viagem(hospedagens: Iterable[Despesa]) -> Set[date]:
    """Conjunto de datas cobertas por alguma hospedagem de viagem."""
    dias: Set[date] = set()
    for hospedagem in hospedagens:
        for deslocamento in range(dias_de_viagem(hospedagem.descricao)):
            dias.add(hospedagem.data + timedelta(days=deslocamento))
    return dias


def limite_diario(categoria: str, em_viagem: bool) -> Decimal:
    """Teto diário de alimentação/transporte, ampliado em viagem (RN-005)."""
    limite = LIMITES_DIARIOS[categoria]
    if em_viagem:
        limite = arredondar_centavos(limite * FATOR_VIAGEM)
    return limite


def avaliar_hospedagem(despesa: Despesa) -> Tuple[str, Decimal, str]:
    """RN-003: ``(status, valor_reembolsado, justificativa)`` da hospedagem."""
    if not hospedagem_de_viagem(despesa):
        return STATUS_REJEITADO, Decimal("0.00"), JUSTIFICATIVA_FORNECEDOR_HOSPEDAGEM
    diarias = numero_de_diarias(despesa.descricao)
    teto = LIMITE_HOSPEDAGEM_POR_DIARIA * diarias
    status, reembolso = aplicar_teto(despesa.valor, teto)
    detalhe = (
        f"{formatar_moeda(LIMITE_HOSPEDAGEM_POR_DIARIA)} por diária x {diarias}"
        if diarias > 1
        else ""
    )
    return status, reembolso, justificar_teto(status, teto, "RN-003", detalhe)


# --------------------------------------------------------------------------
# RN-001 / RN-002 — tetos diários
# --------------------------------------------------------------------------


def aplicar_teto(valor: Decimal, disponivel: Decimal) -> Tuple[str, Decimal]:
    """``(status, reembolso)`` de ``valor`` dado o teto ainda ``disponivel``.

    Integral é ``aprovado``; paga-se menos que o valor é ``parcial``; nada a
    pagar (teto esgotado) é ``rejeitado``.
    """
    reembolso = arredondar_centavos(min(valor, max(disponivel, Decimal("0"))))
    if reembolso == valor:
        return STATUS_APROVADO, reembolso
    if reembolso > 0:
        return STATUS_PARCIAL, reembolso
    return STATUS_REJEITADO, Decimal("0.00")


def formatar_moeda(valor: Decimal) -> str:
    """``Decimal('1234.5')`` -> ``'R$ 1.234,50'``."""
    texto = f"{valor:,.2f}".replace(",", "_").replace(".", ",").replace("_", ".")
    return f"R$ {texto}"


def justificar_teto(status: str, teto: Decimal, regra: str, detalhe: str = "") -> str:
    """Justificativa do resultado de ``aplicar_teto`` (RN-001, RN-002, RN-003)."""
    extra = f", {detalhe}" if detalhe else ""
    if status == STATUS_APROVADO:
        return JUSTIFICATIVA_APROVADO
    if status == STATUS_PARCIAL:
        return f"Valor limitado ao teto de {formatar_moeda(teto)} ({regra}{extra})."
    return (
        f"Teto diário de {formatar_moeda(teto)} já consumido por outras "
        f"despesas do dia ({regra}{extra})."
    )


# --------------------------------------------------------------------------
# RN-004 — nota fiscal
# --------------------------------------------------------------------------


def falta_nota_fiscal(despesa: Despesa) -> bool:
    """RN-004: valor estritamente acima de R$ 100,00 exige nota fiscal."""
    return despesa.valor > LIMITE_SEM_NOTA_FISCAL and not despesa.tem_nota_fiscal
