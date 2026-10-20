"""Constantes e caminhos globais do sistema."""

from decimal import Decimal
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent.parent

# Diretório de persistência dos JSONs de reembolso, validados e resultados.
COLABORADOR_DIR = BASE_DIR / "colaborador"

EXTENSAO_JSON = ".json"
ENCODING = "utf-8"

# Sufixos de estado do arquivo (plan.md, seção 3.2).
SUFIXO_VALIDADO = "_validado"
SUFIXO_RESULTADO = "_resultado"

# Precisão monetária: duas casas decimais (RN-011).
CENTAVOS = Decimal("0.01")
