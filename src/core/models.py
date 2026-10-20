"""Modelos de entrada e saída do motor de reembolso (spec.md, seção 4).

Este módulo só faz *parsing* e normalização de tipos. As regras de negócio
(RN-001 a RN-010) vivem no motor e precisam enxergar dados "ruins" para poder
rejeitá-los com o status correto. Por isso o schema aceita, de propósito:

- valores negativos ou zerados (RN-010);
- categorias fora da política (RN-008);
- competência fora do formato ``YYYY-MM``, vazia ou nula (RN-009).
"""

import re
from datetime import date, datetime
from decimal import ROUND_HALF_UP, Decimal, InvalidOperation
from typing import Annotated, Any, List, Optional

from pydantic import AfterValidator, BaseModel, BeforeValidator, Field, StrictBool

from config import CENTAVOS

_DATA_ISO = re.compile(r"^\d{4}-\d{2}-\d{2}$")


def _para_decimal(valor: Any) -> Decimal:
    """Converte a entrada em ``Decimal`` sem passar por imprecisão de float."""
    if isinstance(valor, bool):
        raise ValueError("valor monetário não pode ser booleano")
    if isinstance(valor, float):
        valor = repr(valor)  # 72.5 -> "72.5"; evita Decimal(72.5) com cauda binária
    if not isinstance(valor, (int, str, Decimal)):
        raise ValueError("valor monetário deve ser número ou texto numérico")
    try:
        decimal = Decimal(valor)
    except InvalidOperation:
        raise ValueError(f"valor monetário inválido: {valor!r}") from None
    if not decimal.is_finite():
        raise ValueError(f"valor monetário deve ser finito: {valor!r}")
    return decimal


def _arredondar_centavos(valor: Decimal) -> Decimal:
    """Duas casas decimais, arredondamento matemático (RN-011)."""
    try:
        arredondado = valor.quantize(CENTAVOS, rounding=ROUND_HALF_UP)
    except InvalidOperation:
        raise ValueError("valor monetário fora do intervalo suportado") from None
    return abs(arredondado) if arredondado == 0 else arredondado  # evita "-0.00"


def _para_data(valor: Any) -> date:
    """Aceita somente datas no formato ``YYYY-MM-DD`` (ou ``date`` puro)."""
    if isinstance(valor, datetime):
        raise ValueError("esperado data (YYYY-MM-DD), recebido data e hora")
    if isinstance(valor, date):
        return valor
    if not isinstance(valor, str) or not _DATA_ISO.match(valor):
        raise ValueError("data deve estar no formato YYYY-MM-DD")
    try:
        return date.fromisoformat(valor)
    except ValueError:
        raise ValueError(f"data inexistente: {valor!r}") from None


Dinheiro = Annotated[
    Decimal,
    BeforeValidator(_para_decimal),
    AfterValidator(_arredondar_centavos),
]
Data = Annotated[date, BeforeValidator(_para_data)]
# Fornecedor é normalizado para minúsculas (spec.md, seção 4 e RN-003).
Fornecedor = Annotated[str, AfterValidator(str.lower)]
TextoObrigatorio = Annotated[str, Field(min_length=1)]


# --------------------------------------------------------------------------
# Entrada
# --------------------------------------------------------------------------


class Colaborador(BaseModel):
    id: TextoObrigatorio
    nome: TextoObrigatorio
    centro_custo: TextoObrigatorio


class Periodo(BaseModel):
    # Obrigatório, mas o formato é validado pelo motor (RN-009): aqui aceita
    # qualquer texto e também ``null``, para que o motor possa rejeitá-lo.
    competencia: Optional[str]
    inicio: Data
    fim: Data


class Despesa(BaseModel):
    id: TextoObrigatorio
    data: Data
    categoria: str
    descricao: str
    fornecedor: Fornecedor
    valor: Dinheiro
    tem_nota_fiscal: StrictBool


class SolicitacaoReembolso(BaseModel):
    colaborador: Colaborador
    periodo: Periodo
    despesas: List[Despesa]


# --------------------------------------------------------------------------
# Saída
# --------------------------------------------------------------------------


class ItemAuditoria(BaseModel):
    id: TextoObrigatorio
    data: Data
    descricao: str
    fornecedor: Fornecedor
    status_item: TextoObrigatorio
    valor_reembolsado: Dinheiro


class HistoricoCompetencia(BaseModel):
    competencia: str
    centro_custo: TextoObrigatorio
    despesas: List[ItemAuditoria]


class ColaboradorResultado(BaseModel):
    id: TextoObrigatorio
    centro_custo: TextoObrigatorio


class ResultadoAuditoria(BaseModel):
    colaborador: ColaboradorResultado
    historico_despesas: List[HistoricoCompetencia]
