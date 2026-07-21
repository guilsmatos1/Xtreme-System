from pathlib import Path

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
def test_wizard_htmx_cria_veiculo(
    page: Page, live_server_url: str, tmp_path: Path
) -> None:
    _login(page, live_server_url)
    page.goto(f"{live_server_url}/ui/compras")

    page.get_by_role("button", name="Nova compra").click()
    expect(page.get_by_role("dialog", name="Nova compra")).to_be_visible()

    page.get_by_label("Nome").fill("Cliente E2E")
    page.get_by_label("Documento").fill("11122233344")
    page.get_by_label("Telefone").fill("11999999999")
    page.get_by_label("Email").fill("cliente-e2e@example.com")

    page.get_by_role("button", name="Próximo").click()
    page.get_by_label("Placa").fill("E2E1A23")
    page.get_by_label("Modelo").fill("Civic E2E")
    page.get_by_label("Cor").fill("Branco")
    page.get_by_label("Ano").fill("2025")
    page.get_by_label("Quilometragem").fill("10")
    page.get_by_label("Investidor").select_option(label="Investidor A")

    page.get_by_role("button", name="Próximo").click()
    page.get_by_label("Valor da compra").fill("95000")
    page.get_by_label("Débitos de veículos").fill("123.45")

    page.get_by_role("button", name="Próximo").click()
    page.get_by_role("button", name="Próximo").click()
    comprovante = tmp_path / "comprovante.pdf"
    comprovante.write_bytes(b"%PDF-1.4\n%%EOF\n")
    page.locator('input[name="comprovantes_pagamento"]').set_input_files(comprovante)

    page.locator("#wizard-salvar").click()

    expect(page.get_by_role("dialog", name="Nova compra")).not_to_be_visible()
    expect(page.get_by_text("Civic E2E")).to_be_visible()
    expect(page.get_by_text("E2E1A23")).to_be_visible()


def _login(page: Page, live_server_url: str) -> None:
    page.goto(f"{live_server_url}/ui/login")
    page.get_by_label("Usuário").fill("admin")
    page.get_by_label("Senha").fill("senha")
    page.get_by_role("button", name="Entrar").click()
    expect(page).to_have_url(f"{live_server_url}/ui/veiculos")
