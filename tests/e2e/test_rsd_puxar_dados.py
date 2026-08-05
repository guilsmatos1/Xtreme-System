import json

import pytest
from playwright.sync_api import Page, Route, expect


def _login(page: Page, live_server_url: str) -> None:
    page.goto(f"{live_server_url}/ui/login")
    page.get_by_test_id("login-username").fill("admin")
    page.get_by_test_id("login-password").fill("senha")
    page.get_by_test_id("login-submit").click()
    expect(page).to_have_url(f"{live_server_url}/ui/veiculos")


def _rsd_success_partial(status_id: str = "rsd-status", prefix: str = "") -> str:
    campos = {
        f"{prefix}placa": "ABC1D23",
        f"{prefix}modelo": "ONIX RSD",
        f"{prefix}marca": "CHEV",
        f"{prefix}ano": 2025,
        f"{prefix}cor": "Preto",
    }
    return (
        f'<div id="{status_id}" class="field field--full rsd-status" '
        f"data-rsd-campos='{json.dumps(campos)}' aria-live=\"polite\">"
        '<div class="alert alert--success" role="alert">Dados carregados do RSD.</div>'
        "</div>"
    )


def _rsd_error_partial(status_id: str, message: str) -> str:
    return (
        f'<div id="{status_id}" class="field field--full rsd-status" '
        'aria-live="polite">'
        f'<div class="alert" role="alert">{message}</div>'
        "</div>"
    )


@pytest.mark.e2e
def test_puxar_dados_substitui_campos_do_modal(
    page: Page, live_server_url: str
) -> None:
    _login(page, live_server_url)
    page.goto(f"{live_server_url}/ui/veiculos")

    page.locator("tr", has_text="Onix").get_by_role(
        "button", name="Editar Onix"
    ).click()
    dialog = page.get_by_role("dialog", name="Editar veículo")
    expect(dialog).to_be_visible()

    page.route(
        "**/ui/rsd/puxar-dados",
        lambda route: route.fulfill(
            status=200,
            content_type="text/html",
            body=_rsd_success_partial(),
        ),
    )
    dialog.get_by_role("button", name="Puxar dados").click()

    expect(dialog.locator('input[name="modelo"]')).to_have_value("ONIX RSD")
    expect(dialog.locator('input[name="marca"]')).to_have_value("CHEV")
    expect(dialog.locator('input[name="ano"]')).to_have_value("2025")
    expect(dialog.locator('input[name="cor"]')).to_have_value("Preto")


@pytest.mark.e2e
def test_puxar_dados_mostra_erro_de_validacao_da_placa(
    page: Page, live_server_url: str
) -> None:
    _login(page, live_server_url)
    page.goto(f"{live_server_url}/ui/veiculos")
    page.locator("tr", has_text="Onix").get_by_role(
        "button", name="Editar Onix"
    ).click()
    dialog = page.get_by_role("dialog", name="Editar veículo")
    placa = dialog.locator('input[name="placa"]')
    placa.fill("XX")

    requisicoes = 0

    def nao_deve_consultar(route: Route) -> None:
        nonlocal requisicoes
        requisicoes += 1
        route.abort()

    page.route("**/ui/rsd/puxar-dados", nao_deve_consultar)
    dialog.get_by_role("button", name="Puxar dados").click()

    expect(dialog.get_by_role("alert")).to_contain_text("Placa inválida")
    assert requisicoes == 0


@pytest.mark.e2e
def test_puxar_dados_mostra_erro_da_consulta(page: Page, live_server_url: str) -> None:
    _login(page, live_server_url)
    page.goto(f"{live_server_url}/ui/veiculos")
    page.locator("tr", has_text="Onix").get_by_role(
        "button", name="Editar Onix"
    ).click()
    dialog = page.get_by_role("dialog", name="Editar veículo")

    page.route(
        "**/ui/rsd/puxar-dados",
        lambda route: route.fulfill(
            status=400,
            content_type="text/html",
            body=_rsd_error_partial(
                "rsd-status", "Placa não encontrada no portal RSD."
            ),
        ),
    )
    dialog.get_by_role("button", name="Puxar dados").click()

    expect(dialog.get_by_role("alert")).to_contain_text(
        "Placa não encontrada no portal RSD."
    )


@pytest.mark.e2e
def test_puxar_dados_substitui_campos_prefixados_do_modal(
    page: Page, live_server_url: str
) -> None:
    _login(page, live_server_url)
    page.goto(f"{live_server_url}/ui/compras")
    page.get_by_test_id("compras-create").click()
    dialog = page.get_by_role("dialog", name="Nova compra")

    dialog.get_by_test_id("compra-wizard-client-name").fill("Cliente RSD")
    dialog.get_by_test_id("compra-wizard-client-document").fill("11122233344")
    dialog.get_by_test_id("compra-wizard-client-phone").fill("11999999999")
    dialog.get_by_test_id("compra-wizard-client-email").fill("rsd@example.com")
    dialog.get_by_test_id("compra-wizard-next").click()
    dialog.get_by_test_id("compra-wizard-vehicle-plate").fill("ABC1D23")

    page.route(
        "**/ui/rsd/puxar-dados",
        lambda route: route.fulfill(
            status=200,
            content_type="text/html",
            body=_rsd_success_partial("rsd-status-compra", "vei_"),
        ),
    )
    dialog.get_by_role("button", name="Puxar dados").click()

    expect(dialog.locator('input[name="vei_modelo"]')).to_have_value("ONIX RSD")
    expect(dialog.locator('input[name="vei_marca"]')).to_have_value("CHEV")
    expect(dialog.locator('input[name="vei_ano"]')).to_have_value("2025")
    expect(dialog.locator('input[name="vei_cor"]')).to_have_value("Preto")
