"""Painel de configuração de colunas (Alpine.data("colunas"), migrado de
static/columns.js#openPanel para templates/_modal_colunas.html).

Cobre o contrato que existia só em código sem teste: abrir o painel,
esconder/mostrar coluna, persistência entre reloads, "Restaurar padrão" e
reordenar por drag sobrevivendo a um swap do htmx (`htmx:afterSwap` reaplica
`ColunasJS.applyPrefs`, que é onde uma divergência entre o array do Alpine e
o DOM apareceria).
"""

import pytest
from playwright.sync_api import Page, expect


def _login(page: Page, live_server_url: str) -> None:
    page.goto(f"{live_server_url}/ui/login")
    page.get_by_test_id("login-username").fill("admin")
    page.get_by_test_id("login-password").fill("senha")
    page.get_by_test_id("login-submit").click()
    expect(page).to_have_url(f"{live_server_url}/ui/veiculos")


@pytest.mark.e2e
def test_ocultar_coluna_esconde_thead_e_tbody(page: Page, live_server_url: str) -> None:
    _login(page, live_server_url)

    coluna_th = page.locator('table[data-table="veiculos"] thead th[data-col="modelo"]')
    expect(coluna_th).to_be_visible()

    page.locator("[data-cols-btn]").click()
    modal = page.get_by_test_id("modal-colunas")
    expect(modal).to_be_visible()

    modal.locator("li[data-idx] label", has_text="Modelo").locator(
        'input[type="checkbox"]'
    ).uncheck()
    page.get_by_test_id("colunas-fechar").click()
    expect(modal).not_to_be_visible()

    expect(coluna_th).to_have_class("col-hidden")


@pytest.mark.e2e
def test_preferencia_de_coluna_persiste_apos_reload(
    page: Page, live_server_url: str
) -> None:
    _login(page, live_server_url)

    page.locator("[data-cols-btn]").click()
    modal = page.get_by_test_id("modal-colunas")
    modal.locator("li[data-idx] label", has_text="Marca").locator(
        'input[type="checkbox"]'
    ).uncheck()
    page.get_by_test_id("colunas-fechar").click()

    page.reload()
    coluna_th = page.locator('table[data-table="veiculos"] thead th[data-col="marca"]')
    expect(coluna_th).to_have_class("col-hidden")


@pytest.mark.e2e
def test_restaurar_padrao_devolve_coluna_oculta(
    page: Page, live_server_url: str
) -> None:
    _login(page, live_server_url)

    page.locator("[data-cols-btn]").click()
    modal = page.get_by_test_id("modal-colunas")
    modal.locator("li[data-idx] label", has_text="Modelo").locator(
        'input[type="checkbox"]'
    ).uncheck()
    page.get_by_test_id("colunas-fechar").click()

    coluna_th = page.locator('table[data-table="veiculos"] thead th[data-col="modelo"]')
    expect(coluna_th).to_have_class("col-hidden")

    page.locator("[data-cols-btn]").click()
    page.get_by_test_id("colunas-restaurar").click()
    page.get_by_test_id("colunas-fechar").click()

    expect(coluna_th).not_to_have_class("col-hidden")


@pytest.mark.e2e
def test_reordenar_por_drag_sobrevive_a_swap_do_htmx(
    page: Page, live_server_url: str
) -> None:
    _login(page, live_server_url)

    def primeira_coluna_gerenciavel() -> str:
        val = page.locator(
            'table[data-table="veiculos"] thead th[data-col]:not([data-col-fixed])'
        ).first.get_attribute("data-col")
        assert val is not None
        return val

    assert primeira_coluna_gerenciavel() == "placa"

    page.locator("[data-cols-btn]").click()
    modal = page.get_by_test_id("modal-colunas")
    expect(modal).to_be_visible()
    itens = modal.locator("li[data-idx]")
    origem = itens.nth(0)
    destino = itens.nth(1)
    expect(destino).to_be_visible()
    destino_box = destino.bounding_box()
    assert destino_box

    # Playwright não simula o pipeline nativo de drag-and-drop do browser a
    # partir de mouse.move/down/up; o padrão documentado é disparar os
    # eventos HTML5 diretamente com um DataTransfer compartilhado.
    data_transfer = page.evaluate_handle("new DataTransfer()")
    origem.dispatch_event("dragstart", {"dataTransfer": data_transfer})
    destino.dispatch_event(
        "dragover",
        {
            "dataTransfer": data_transfer,
            "clientY": destino_box["y"] + destino_box["height"] / 2,
        },
    )
    origem.dispatch_event("dragend", {"dataTransfer": data_transfer})

    page.get_by_test_id("colunas-fechar").click()

    assert primeira_coluna_gerenciavel() == "modelo"

    # Força um swap do htmx (busca) e confirma que a ordem sobreviveu — é
    # onde applyPrefs roda de novo e uma divergência array/DOM apareceria.
    page.get_by_placeholder("Buscar por qualquer campo…").fill("a")
    page.wait_for_timeout(400)
    assert primeira_coluna_gerenciavel() == "modelo"
