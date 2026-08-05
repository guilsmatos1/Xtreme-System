"""Bloqueio de campos required no avanço do wizard (validStep em components.js).

Regressão de um bug de escopo do Alpine: `validStep` buscava `.wizard-step`
dentro de `this.$el`, que nas expressões `x-on` dos filhos é o elemento do
evento (o botão "Próximo"), não a `<form>`. O querySelector não achava o passo,
`validStep` retornava true por falta de passo e o wizard avançava com todos os
campos obrigatórios vazios — nos quatro wizards (venda, compra, consignação,
veículo).
"""

import pytest
from playwright.sync_api import Page, expect


def _login(page: Page, live_server_url: str) -> None:
    page.goto(f"{live_server_url}/ui/login")
    page.get_by_test_id("login-username").fill("admin")
    page.get_by_test_id("login-password").fill("senha")
    page.get_by_test_id("login-submit").click()
    expect(page).to_have_url(f"{live_server_url}/ui/veiculos")


def _passo_ativo(page: Page) -> str:
    ativo = page.locator("#modal .wizard-step.is-active")
    return ativo.get_attribute("data-step") or ""


@pytest.mark.e2e
def test_wizard_venda_nao_avanca_com_campos_obrigatorios_vazios(
    page: Page, live_server_url: str
) -> None:
    _login(page, live_server_url)
    page.goto(f"{live_server_url}/ui/vendas")
    page.get_by_test_id("vendas-create").click()
    expect(page.get_by_role("dialog", name="Nova venda")).to_be_visible()

    assert _passo_ativo(page) == "1"
    page.get_by_test_id("venda-wizard-next").click()
    assert _passo_ativo(page) == "1", "avançou com nome/documento/telefone vazios"

    # Só o nome não basta: documento e telefone também são required.
    page.get_by_test_id("venda-wizard-client-name").fill("Cliente Validação")
    page.get_by_test_id("venda-wizard-next").click()
    assert _passo_ativo(page) == "1", "avançou com documento/telefone vazios"

    page.get_by_test_id("venda-wizard-client-document").fill("55566677788")
    page.get_by_test_id("venda-wizard-client-phone").fill("11977777777")
    page.get_by_test_id("venda-wizard-next").click()
    assert _passo_ativo(page) == "2", "não avançou com o passo 1 completo"


@pytest.mark.e2e
def test_wizard_compra_nao_avanca_com_campos_obrigatorios_vazios(
    page: Page, live_server_url: str
) -> None:
    _login(page, live_server_url)
    page.goto(f"{live_server_url}/ui/compras")
    page.get_by_test_id("compras-create").click()
    expect(page.get_by_role("dialog", name="Nova compra")).to_be_visible()

    assert _passo_ativo(page) == "1"
    page.get_by_test_id("compra-wizard-next").click()
    assert _passo_ativo(page) == "1", "avançou com o passo do cliente vazio"

    page.get_by_test_id("compra-wizard-client-name").fill("Vendedor Validação")
    page.get_by_test_id("compra-wizard-client-document").fill("44455566677")
    page.get_by_test_id("compra-wizard-client-phone").fill("11944444444")
    page.get_by_test_id("compra-wizard-next").click()
    assert _passo_ativo(page) == "2"

    # Passo do veículo: placa/modelo/cor/ano são required.
    page.get_by_test_id("compra-wizard-next").click()
    assert _passo_ativo(page) == "2", "avançou com os dados do veículo vazios"
