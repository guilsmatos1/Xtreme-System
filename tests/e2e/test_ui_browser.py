from pathlib import Path

import pytest
from playwright.sync_api import Page, expect


@pytest.mark.e2e
def test_login_admin_abre_veiculos(page: Page, live_server_url: str) -> None:
    page.goto(f"{live_server_url}/ui/login")

    page.get_by_test_id("login-username").fill("admin")
    page.get_by_test_id("login-password").fill("senha")
    page.get_by_test_id("login-submit").click()

    expect(page).to_have_url(f"{live_server_url}/ui/veiculos")
    expect(page.get_by_role("heading", name="Veículos")).to_be_visible()
    expect(page.get_by_text("Onix")).to_be_visible()


@pytest.mark.e2e
def test_wizard_htmx_cria_veiculo(
    page: Page, live_server_url: str, tmp_path: Path
) -> None:
    _login(page, live_server_url)
    page.goto(f"{live_server_url}/ui/compras")

    page.get_by_test_id("compras-create").click()
    expect(page.get_by_role("dialog", name="Nova compra")).to_be_visible()

    page.get_by_test_id("compra-wizard-client-name").fill("Cliente E2E")
    page.get_by_test_id("compra-wizard-client-document").fill("11122233344")
    page.get_by_test_id("compra-wizard-client-phone").fill("11999999999")
    page.get_by_test_id("compra-wizard-client-email").fill("cliente-e2e@example.com")

    page.get_by_test_id("compra-wizard-next").click()
    page.get_by_test_id("compra-wizard-vehicle-plate").fill("EZE1A23")
    page.get_by_test_id("compra-wizard-vehicle-model").fill("Civic E2E")
    page.get_by_test_id("compra-wizard-vehicle-color").fill("Branco")
    page.get_by_test_id("compra-wizard-vehicle-year").fill("2025")

    page.get_by_test_id("compra-wizard-next").click()
    page.get_by_test_id("compra-wizard-purchase-value").fill("95000")
    page.get_by_test_id("compra-wizard-vehicle-debts").fill("123.45")

    page.get_by_test_id("compra-wizard-next").click()
    page.get_by_test_id("compra-wizard-vehicle-mileage").fill("10")
    page.get_by_test_id("compra-wizard-vehicle-investor").select_option(
        label="Investidor A"
    )

    page.get_by_test_id("compra-wizard-next").click()
    comprovante = tmp_path / "comprovante.pdf"
    comprovante.write_bytes(b"%PDF-1.4\n%%EOF\n")
    page.get_by_test_id("compra-wizard-payment-receipts").set_input_files(comprovante)

    page.get_by_test_id("compra-wizard-save").click()

    expect(page.get_by_role("dialog", name="Nova compra")).not_to_be_visible()
    expect(page.get_by_role("status")).to_contain_text("Alterações salvas com sucesso")


@pytest.mark.e2e
def test_modal_servidor_tem_foco_escape_e_focus_trap(
    page: Page, live_server_url: str
) -> None:
    _login(page, live_server_url)
    page.goto(f"{live_server_url}/ui/compras")

    opener = page.get_by_test_id("compras-create")
    opener.click()
    dialog = page.get_by_role("dialog", name="Nova compra")

    expect(dialog).to_be_visible()
    expect(page.get_by_test_id("compra-wizard-client-select")).to_be_focused()

    close_button = dialog.get_by_test_id("compra-wizard-close")
    last_button = dialog.get_by_test_id("compra-wizard-next")
    last_button.focus()
    page.keyboard.press("Tab")
    expect(close_button).to_be_focused()

    page.keyboard.press("Escape")
    expect(dialog).not_to_be_visible()
    expect(opener).to_be_focused()


def _login(page: Page, live_server_url: str) -> None:
    page.goto(f"{live_server_url}/ui/login")
    page.get_by_test_id("login-username").fill("admin")
    page.get_by_test_id("login-password").fill("senha")
    page.get_by_test_id("login-submit").click()
    expect(page).to_have_url(f"{live_server_url}/ui/veiculos")
