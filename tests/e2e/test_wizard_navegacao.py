"""Navegação do wizard multi-step, agora dirigida por Alpine (components.js).

Cobre a visibilidade dos botões conforme o passo — comportamento que antes
estava triplicado em JS inline e hoje vem do componente único wizard().

O wizard de _form_veiculo.html usa o mesmo componente, mas não é testável pela
UI: veiculos.html não tem botão de criação (ao contrário de vendas.html e
compras.html, que fazem hx-get de /ui/{recurso}/novo), então GET
/ui/veiculos/novo existe como rota mas nenhum usuário consegue abri-lo.
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
def test_wizard_venda_mostra_salvar_apenas_no_ultimo_passo(
    page: Page, live_server_url: str
) -> None:
    _login(page, live_server_url)
    page.goto(f"{live_server_url}/ui/vendas")
    page.get_by_test_id("vendas-create").click()
    expect(page.get_by_role("dialog", name="Nova venda")).to_be_visible()

    proximo = page.get_by_test_id("venda-wizard-next")
    salvar = page.get_by_test_id("venda-wizard-save")
    expect(proximo).to_be_visible()
    expect(salvar).not_to_be_visible()

    page.get_by_test_id("venda-wizard-client-name").fill("Cliente Wizard E2E")
    page.get_by_test_id("venda-wizard-client-document").fill("55566677788")
    page.get_by_test_id("venda-wizard-client-phone").fill("11977777777")
    proximo.click()

    page.get_by_test_id("venda-wizard-vehicle-select").select_option(
        label="ABC1234 — Onix"
    )
    page.locator('input[name="km"]').fill("12000")
    page.locator('input[name="debitos"]').fill("0")
    proximo.click()
    proximo.click()

    page.get_by_test_id("venda-wizard-value").fill("130000")
    page.get_by_test_id("venda-wizard-payment-method").select_option("pix")
    page.get_by_test_id("venda-wizard-valor-documento").fill("130000")
    proximo.click()

    # Último passo (5 de 5): "Salvar" aparece e "Próximo" some.
    expect(salvar).to_be_visible()
    expect(proximo).not_to_be_visible()
