from __future__ import annotations

import html

import pytest
from playwright.sync_api import Locator, Page, Route, expect


def _login(page: Page, live_server_url: str) -> None:
    page.goto(f"{live_server_url}/ui/login")
    page.get_by_test_id("login-username").fill("admin")
    page.get_by_test_id("login-password").fill("senha")
    page.get_by_test_id("login-submit").click()
    expect(page).to_have_url(f"{live_server_url}/ui/veiculos")


def _open_rsd(page: Page, live_server_url: str) -> Locator:
    page.goto(f"{live_server_url}/ui/configuracoes")
    page.get_by_role("tab").filter(has_text="RSD").click()
    panel = page.locator("section.settings-tabs__panel--rsd")
    expect(panel).to_be_visible()
    return panel


def _rsd_test_response(*, message: str, success: bool) -> str:
    result_class = "rsd-test-result--success" if success else "rsd-test-result--error"
    result_role = "status" if success else "alert"
    result_message = (
        "Teste aprovado para este rascunho; ainda não salvo" if success else message
    )
    return f"""
    <div class="rsd-test-result {result_class}" role="{result_role}">
      <span>{html.escape(result_message)}</span>
      <span>{html.escape(message)}</span>
    </div>
    """


@pytest.mark.e2e
def test_portal_rsd_preserva_rascunho_em_erro_timeout_e_sucesso(
    page: Page, live_server_url: str
) -> None:
    _login(page, live_server_url)
    panel = _open_rsd(page, live_server_url)
    email = "loja-rsd@example.com"
    base_url = "https://rsd.test"
    senha = "senha-nao-deve-voltar"
    respostas = iter(
        [
            (400, "E-mail ou senha inválidos no portal RSD.", False),
            (400, "O portal RSD não respondeu a tempo.", False),
            (200, "Conexão com o portal RSD OK.", True),
        ]
    )
    requests = 0

    def interceptar_teste(route: Route) -> None:
        nonlocal requests
        requests += 1
        status, message, success = next(respostas)
        route.fulfill(
            status=status,
            headers={"Content-Type": "text/html; charset=utf-8"},
            body=_rsd_test_response(message=message, success=success),
        )

    page.route("**/ui/configuracoes/rsd/teste", interceptar_teste)
    form = panel.locator("form").first
    form.locator('input[name="email"]').fill(email)
    form.locator('input[name="senha"]').fill(senha)
    form.locator('input[name="base_url"]').fill(base_url)

    for expected in (
        "E-mail ou senha inválidos",
        "O portal RSD não respondeu a tempo",
        "Teste aprovado para este rascunho; ainda não salvo",
    ):
        page.locator('form:has(button[formaction$="/teste"])').first.get_by_role(
            "button", name="Testar conexão"
        ).click()
        if expected == "Teste aprovado para este rascunho; ainda não salvo":
            expect(page.get_by_text(expected)).to_be_visible()
        else:
            expect(page.get_by_role("alert")).to_contain_text(expected)
        expect(panel.locator('input[name="email"]')).to_have_value(email)
        expect(panel.locator('input[name="base_url"]')).to_have_value(base_url)
        expect(panel.locator('input[name="senha"]')).to_have_value(senha)
        if expected != "Teste aprovado para este rascunho; ainda não salvo":
            page.locator('input[name="senha"]').fill(senha)

    assert requests == 3
    page.unroute("**/ui/configuracoes/rsd/teste", interceptar_teste)
    panel = _open_rsd(page, live_server_url)
    expect(panel.get_by_text("Integração não configurada")).to_be_visible()


@pytest.mark.e2e
def test_portal_rsd_salva_recarrega_preserva_senha_e_revoga(
    page: Page, live_server_url: str
) -> None:
    _login(page, live_server_url)
    panel = _open_rsd(page, live_server_url)
    form = panel.locator("form").first
    form.locator('input[name="email"]').fill("loja-rsd@example.com")
    form.locator('input[name="senha"]').fill("senha-segura")
    form.locator('input[name="base_url"]').fill("https://rsd.test")
    form.get_by_role("button", name="Salvar", exact=True).click()
    expect(page.get_by_role("alert")).to_contain_text("Configurações RSD salvas")
    expect(page.locator('input[name="senha"]')).to_have_value("")

    page.reload()
    panel = _open_rsd(page, live_server_url)
    expect(panel.get_by_text("Credenciais salvas — teste pendente")).to_be_visible()
    form = panel.locator("form").first
    form.locator('input[name="email"]').fill("loja-rsd-nova@example.com")
    form.locator('input[name="senha"]').fill("")
    form.get_by_role("button", name="Salvar", exact=True).click()
    expect(page.get_by_role("alert")).to_contain_text("Configurações RSD salvas")
    expect(page.locator('input[name="senha"]')).to_have_value("")

    page.on("dialog", lambda dialog: dialog.accept())
    panel.get_by_role("button", name="Remover credenciais RSD").click()
    expect(page.get_by_role("alert")).to_contain_text("revogada e removida")
    expect(page.get_by_role("button", name="Revogar credencial")).to_have_count(0)


@pytest.mark.e2e
def test_portal_rsd_configura_controles_durante_teste(
    page: Page, live_server_url: str
) -> None:
    _login(page, live_server_url)
    panel = _open_rsd(page, live_server_url)
    requests = 0

    def teste_lento(route: Route) -> None:
        nonlocal requests
        requests += 1
        route.fulfill(
            status=200,
            headers={"Content-Type": "text/html; charset=utf-8"},
            body=_rsd_test_response(
                message="Conexão com o portal RSD OK.", success=True
            ),
        )

    page.route("**/ui/configuracoes/rsd/teste", teste_lento)
    panel.locator('input[name="email"]').fill("loja-rsd@example.com")
    panel.locator('input[name="senha"]').fill("senha-segura")
    expect(panel.get_by_role("button", name="Testar conexão")).to_have_attribute(
        "x-bind:disabled", "testando"
    )
    expect(panel.get_by_role("button", name="Salvar", exact=True)).to_have_attribute(
        "x-bind:disabled", "testando"
    )
    panel.get_by_role("button", name="Testar conexão").click()
    expect(page.get_by_text("Conexão com o portal RSD OK")).to_be_visible()
    assert requests == 1
