"""Cobertura do campo de referência (typeahead) alimentado por static/reference.js.

O formulário de veículo chega por swap do HTMX, depois do load inicial da
página. Antes da extração para reference.js o <script> vinha inline dentro do
próprio fragmento e executava junto com o swap; agora o arquivo é carregado uma
vez e reinicializa via htmx:load. Este teste existe para travar exatamente esse
contrato — sem ele, o typeahead pode morrer silenciosamente ao abrir o modal.
"""

import pytest
from playwright.sync_api import Page, expect


@pytest.mark.e2e
def test_campo_referencia_carrega_apos_swap_htmx(
    page: Page, live_server_url: str
) -> None:
    page.goto(f"{live_server_url}/ui/login")
    page.get_by_test_id("login-username").fill("admin")
    page.get_by_test_id("login-password").fill("senha")
    page.get_by_test_id("login-submit").click()
    expect(page).to_have_url(f"{live_server_url}/ui/veiculos")

    # O modal (e portanto o campo de referência) só existe após o swap.
    linha = page.locator("tr", has_text="Onix")
    linha.get_by_role("button", name="Editar Onix").click()
    expect(page.get_by_role("dialog", name="Editar veículo")).to_be_visible()

    # O investidor semeado pelo conftest precisa aparecer no datalist, o que só
    # acontece se reference.js reinicializou o campo depois do swap.
    expect(
        page.locator('#investidores-list option[value="Investidor A"]')
    ).to_have_count(1)

    page.get_by_test_id("veiculo-wizard-next").click()

    # E selecionar o rótulo precisa preencher o hidden com o id correspondente.
    investidor_input = page.locator("#investidor-input")
    investidor_input.fill("Investidor A")
    investidor_input.dispatch_event("change")
    expect(page.locator("#investidor-search")).not_to_have_value("")
