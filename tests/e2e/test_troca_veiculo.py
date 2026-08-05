"""Transições do bloco de troca de veículo (Alpine.data("trocaVeiculo")).

Os dois testes que já existiam em test_ui_browser.py cobrem os caminhos de
sucesso: cadastrar um veículo novo na troca, e escolher um veículo existente.
Nenhum cobria **desligar** a troca, que é a transição com mais efeitos
colaterais — limpa o id, o texto da busca, o modo de cadastro e os valores do
bloco inline. É o ramo mais fácil de quebrar numa reescrita.
"""

import pytest
from playwright.sync_api import Page, expect


def _login(page: Page, live_server_url: str) -> None:
    page.goto(f"{live_server_url}/ui/login")
    page.get_by_test_id("login-username").fill("admin")
    page.get_by_test_id("login-password").fill("senha")
    page.get_by_test_id("login-submit").click()
    expect(page).to_have_url(f"{live_server_url}/ui/veiculos")


def _abrir_passo_troca(page: Page, live_server_url: str) -> None:
    page.goto(f"{live_server_url}/ui/vendas")
    page.get_by_test_id("vendas-create").click()
    expect(page.get_by_role("dialog", name="Nova venda")).to_be_visible()

    page.get_by_test_id("venda-wizard-client-name").fill("Cliente Troca Reset")
    page.get_by_test_id("venda-wizard-client-document").fill("99988877766")
    page.get_by_test_id("venda-wizard-client-phone").fill("11955555555")
    page.get_by_test_id("venda-wizard-next").click()

    page.get_by_test_id("venda-wizard-vehicle-select").select_option(
        label="ABC1234 — Onix"
    )
    page.locator('input[name="km"]').fill("12000")
    page.locator('input[name="debitos"]').fill("0")
    page.get_by_test_id("venda-wizard-next").click()


@pytest.mark.e2e
def test_desligar_troca_limpa_estado_do_cadastro_inline(
    page: Page, live_server_url: str
) -> None:
    _login(page, live_server_url)
    _abrir_passo_troca(page, live_server_url)

    select = page.locator("#houve-troca")
    bloco = page.locator("#novo-veiculo-troca-campos")
    placa = page.locator('input[name="veic_troca_placa"]')
    modo_novo = page.locator("#veiculo-troca-novo")

    select.select_option("true")
    expect(bloco).to_be_visible()
    expect(placa).to_be_enabled()
    placa.fill("RST4C56")
    expect(modo_novo).to_have_value("1")

    select.select_option("false")

    # Some da tela, para de ser enviado, e o valor digitado é descartado.
    expect(bloco).not_to_be_visible()
    expect(modo_novo).to_have_value("0")
    expect(placa).to_have_value("")

    # Religar mostra novamente o cadastro novo.
    select.select_option("true")
    expect(bloco).to_be_visible()
    expect(placa).to_have_value("")
    expect(modo_novo).to_have_value("1")


@pytest.mark.e2e
def test_campos_da_troca_so_aparecem_com_a_troca_ligada(
    page: Page, live_server_url: str
) -> None:
    _login(page, live_server_url)
    _abrir_passo_troca(page, live_server_url)

    cadastro = page.locator("#novo-veiculo-troca-campos")

    expect(cadastro).not_to_be_visible()
    expect(page.locator("#veiculo-troca-input")).to_have_count(0)
    expect(page.get_by_role("button", name="Cadastrar novo veículo")).to_have_count(0)

    page.locator("#houve-troca").select_option("true")
    expect(cadastro).to_be_visible()
