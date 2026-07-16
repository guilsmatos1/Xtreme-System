import pytest
from playwright.sync_api import Page, expect


@pytest.mark.e2e
def test_login_admin_abre_veiculos(page: Page, live_server_url: str) -> None:
    page.goto(f"{live_server_url}/ui/login")

    page.get_by_label("Usuário").fill("admin")
    page.get_by_label("Senha").fill("senha")
    page.get_by_role("button", name="Entrar").click()

    expect(page).to_have_url(f"{live_server_url}/ui/veiculos")
    expect(page.get_by_role("heading", name="Veículos")).to_be_visible()
    expect(page.get_by_text("Onix")).to_be_visible()


@pytest.mark.e2e
def test_wizard_htmx_cria_veiculo(page: Page, live_server_url: str) -> None:
    _login(page, live_server_url)
    page.goto(f"{live_server_url}/ui/compras")

    page.get_by_role("button", name="Nova compra").click()
    expect(page.get_by_role("dialog", name="Novo veículo")).to_be_visible()
    expect(page.locator("#wizard-step-atual")).to_have_text("1")

    page.get_by_role("button", name="Próximo").click()
    page.get_by_label("Placa").fill("E2E1A23")
    page.get_by_label("Modelo").fill("Civic E2E")
    page.get_by_label("Cor").fill("Branco")
    page.get_by_label("Ano").fill("2025")
    page.get_by_label("Quilometragem").fill("10")

    page.get_by_role("button", name="Próximo").click()
    page.get_by_label("Preço de Compra (R$)").fill("95000")
    page.get_by_label("Débitos (R$)").fill("123.45")

    page.get_by_role("button", name="Próximo").click()
    page.get_by_label("Nome").fill("Cliente E2E")
    page.get_by_label("CPF").fill("11122233344")
    page.get_by_label("Telefone").fill("11999999999")
    page.get_by_label("Email").fill("cliente-e2e@example.com")

    page.locator("#wizard-salvar").click()

    expect(page.get_by_role("dialog", name="Novo veículo")).not_to_be_visible()
    expect(page.get_by_text("Civic E2E")).to_be_visible()
    expect(page.get_by_text("E2E1A23")).to_be_visible()


def _login(page: Page, live_server_url: str) -> None:
    page.goto(f"{live_server_url}/ui/login")
    page.get_by_label("Usuário").fill("admin")
    page.get_by_label("Senha").fill("senha")
    page.get_by_role("button", name="Entrar").click()
    expect(page).to_have_url(f"{live_server_url}/ui/veiculos")
