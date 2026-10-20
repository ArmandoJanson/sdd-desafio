"""Estrutura do projeto e constantes globais (T-001)."""

from decimal import Decimal

import config


def test_estrutura_de_diretorios_do_projeto():
    for pasta in ("src/core", "src/storage", "src/ui", "tests", "colaborador"):
        assert (config.BASE_DIR / pasta).is_dir(), pasta


def test_pasta_de_persistencia():
    assert config.COLABORADOR_DIR == config.BASE_DIR / "colaborador"
    assert config.COLABORADOR_DIR.is_dir()


def test_constantes_de_nomenclatura():
    assert config.EXTENSAO_JSON == ".json"
    assert config.SUFIXO_VALIDADO == "_validado"
    assert config.SUFIXO_RESULTADO == "_resultado"


def test_precisao_monetaria_e_decimal_com_duas_casas():
    assert isinstance(config.CENTAVOS, Decimal)
    assert config.CENTAVOS == Decimal("0.01")
