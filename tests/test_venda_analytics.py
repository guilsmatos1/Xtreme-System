"""Unit tests for venda analytics helpers."""

from datetime import date

import pytest

from xtreme_system.venda import analytics as venda


@pytest.mark.parametrize(
    ("hoje", "meses", "esperado"),
    [
        (date(2026, 7, 31), 6, date(2026, 2, 1)),
        (date(2026, 1, 1), 12, date(2025, 2, 1)),
    ],
)
def test_inicio_janela_meses_inclui_mes_atual(
    hoje: date, meses: int, esperado: date
) -> None:
    assert venda._inicio_janela_meses(hoje, meses) == esperado  # noqa: SLF001
