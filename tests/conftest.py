"""Fixtures compartilhadas."""

from datetime import date

import pytest

from storage import service

HOJE_FIXO = date(2026, 12, 31)


@pytest.fixture(autouse=True)
def relogio_fixo(monkeypatch):
    """Fixa "hoje" para os testes não dependerem do dia em que rodam (RN-012).

    Dezembro de 2026 mantém passadas todas as competências usadas nos testes.
    """
    monkeypatch.setattr(service, "hoje", lambda: HOJE_FIXO)
