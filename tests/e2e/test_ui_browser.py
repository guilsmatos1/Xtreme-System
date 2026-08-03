import re
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


@pytest.mark.e2e
def test_modal_cliente_cadastro_cria_cliente(page: Page, live_server_url: str) -> None:
    _login(page, live_server_url)
    page.goto(f"{live_server_url}/ui/clientes/todos")

    page.get_by_test_id("clientes-create").click()
    expect(page.get_by_role("dialog", name="Novo cliente")).to_be_visible()

    page.get_by_test_id("cliente-form-name").fill("Cliente Modal E2E")
    page.get_by_test_id("cliente-form-document").fill("11122233344")
    page.get_by_test_id("cliente-form-type").select_option(label="Pessoa Fisica")
    page.get_by_test_id("cliente-form-email").fill("cliente-modal-e2e@example.com")
    page.get_by_test_id("cliente-form-phone").fill("11999999999")

    page.get_by_test_id("cliente-form-save").click()

    expect(page.get_by_role("dialog", name="Novo cliente")).not_to_be_visible()
    expect(page.get_by_role("status")).to_contain_text("Alterações salvas com sucesso")
    expect(page.get_by_text("Cliente Modal E2E")).to_be_visible()


@pytest.mark.e2e
def test_modal_veiculo_editar_atualiza_preco(page: Page, live_server_url: str) -> None:
    _login(page, live_server_url)
    page.goto(f"{live_server_url}/ui/veiculos")

    linha = page.locator("tr", has_text="Onix")
    linha.get_by_role("button", name="Editar Onix").click()

    expect(page.get_by_role("dialog", name="Editar veículo")).to_be_visible()
    preco = page.get_by_test_id("veiculo-edit-preco")
    preco.fill("")
    preco.fill("90000")
    page.get_by_test_id("veiculo-edit-save").click()

    expect(page.get_by_role("dialog", name="Editar veículo")).not_to_be_visible()
    expect(page.get_by_role("status")).to_contain_text("Alterações salvas com sucesso")
    expect(page.locator("tr", has_text="Onix")).to_contain_text("R$ 90.000,00")


@pytest.mark.e2e
def test_modal_cliente_vendedor_sem_compra_mostra_vazio(
    page: Page, live_server_url: str
) -> None:
    _login(page, live_server_url)
    page.goto(f"{live_server_url}/ui/veiculos")

    linha = page.locator("tr", has_text="Onix")
    linha.get_by_role("button", name="Cliente vendedor de Onix").click()

    dialog = page.get_by_role("dialog", name="Cliente vendedor")
    expect(dialog).to_be_visible()
    expect(dialog).to_contain_text(
        "Este veículo ainda não possui uma compra vinculada."
    )


@pytest.mark.e2e
def test_modal_venda_wizard_cria_venda(page: Page, live_server_url: str) -> None:
    _login(page, live_server_url)
    page.goto(f"{live_server_url}/ui/vendas")

    page.get_by_test_id("vendas-create").click()
    expect(page.get_by_role("dialog", name="Nova venda")).to_be_visible()

    page.get_by_test_id("venda-wizard-client-name").fill("Cliente Venda E2E")
    page.get_by_test_id("venda-wizard-client-document").fill("22233344455")
    page.get_by_test_id("venda-wizard-client-phone").fill("11999999999")
    page.get_by_test_id("venda-wizard-next").click()

    page.get_by_test_id("venda-wizard-vehicle-select").select_option(
        label="ABC1234 — Onix"
    )
    page.get_by_test_id("venda-wizard-next").click()

    page.get_by_test_id("venda-wizard-value").fill("130000")
    page.get_by_test_id("venda-wizard-payment-method").fill("Pix")
    page.get_by_test_id("venda-wizard-next").click()

    page.get_by_test_id("venda-wizard-save").click()

    expect(page.get_by_role("dialog", name="Nova venda")).not_to_be_visible()
    expect(page.get_by_role("status")).to_contain_text("Alterações salvas com sucesso")
    expect(page.get_by_text("Cliente Venda E2E")).to_be_visible()


@pytest.mark.e2e
def test_modal_venda_wizard_cadastra_veiculo_novo_na_troca(
    page: Page, live_server_url: str
) -> None:
    _login(page, live_server_url)
    page.goto(f"{live_server_url}/ui/vendas")

    page.get_by_test_id("vendas-create").click()
    expect(page.get_by_role("dialog", name="Nova venda")).to_be_visible()

    page.get_by_test_id("venda-wizard-client-name").fill("Cliente Troca E2E")
    page.get_by_test_id("venda-wizard-client-document").fill("44455566677")
    page.get_by_test_id("venda-wizard-client-phone").fill("11977777777")
    page.get_by_test_id("venda-wizard-next").click()

    page.get_by_test_id("venda-wizard-vehicle-select").select_option(
        label="ABC1234 — Onix"
    )
    page.get_by_test_id("venda-wizard-next").click()

    page.get_by_test_id("venda-wizard-value").fill("130000")
    page.get_by_test_id("venda-wizard-payment-method").fill("Pix")
    page.get_by_test_id("venda-wizard-next").click()

    page.locator("#houve-troca").check()
    cadastrar = page.get_by_role("button", name="Cadastrar novo veículo")
    expect(cadastrar).to_be_visible()
    cadastrar.click()

    page.locator('select[name="veic_troca_tipo"]').select_option("carro")
    page.locator('input[name="veic_troca_placa"]').fill("TRC1234")
    page.locator('input[name="veic_troca_modelo"]').fill("Gol Troca E2E")
    page.locator('input[name="veic_troca_cor"]').fill("Branco")
    page.locator('input[name="veic_troca_ano"]').fill("2018")
    page.locator('input[name="veic_troca_preco"]').fill("30000")
    page.locator('select[name="veic_troca_investidor_id"]').select_option(
        label="Investidor A"
    )
    page.get_by_test_id("venda-wizard-save").click()

    expect(page.get_by_role("dialog", name="Nova venda")).not_to_be_visible()
    expect(page.get_by_role("status")).to_contain_text("Alterações salvas com sucesso")

    page.goto(f"{live_server_url}/ui/veiculos")
    expect(page.get_by_text("Gol Troca E2E")).to_be_visible()
    expect(page.get_by_text("TRC1234")).to_be_visible()


@pytest.mark.e2e
def test_modal_venda_troca_veiculo_existente_desabilita_cadastro_inline(
    page: Page, live_server_url: str
) -> None:
    _login(page, live_server_url)
    page.goto(f"{live_server_url}/ui/vendas")

    page.get_by_test_id("vendas-create").click()
    page.get_by_test_id("venda-wizard-client-name").fill("Cliente Existente E2E")
    page.get_by_test_id("venda-wizard-client-document").fill("55566677788")
    page.get_by_test_id("venda-wizard-client-phone").fill("11966666666")
    page.get_by_test_id("venda-wizard-next").click()
    vehicle_select = page.get_by_test_id("venda-wizard-vehicle-select")
    expect(vehicle_select).to_be_visible()
    vehicle_select.select_option(label="ABC1234 — Onix")
    page.get_by_test_id("venda-wizard-next").click()
    page.get_by_test_id("venda-wizard-value").fill("130000")
    page.get_by_test_id("venda-wizard-payment-method").fill("Pix")
    page.get_by_test_id("venda-wizard-next").click()

    page.locator("#houve-troca").check()
    busca = page.locator("#veiculo-troca-input")
    busca.fill("ABC1234")
    opcao = page.locator('#veiculos-troca-list option[value="ABC1234 — Onix"]')
    expect(opcao).to_have_count(1)
    busca.evaluate(
        """(input) => {
            input.value = 'ABC1234 — Onix';
            input.dispatchEvent(new Event('change', {bubbles: true}));
        }"""
    )

    expect(page.locator("#veiculo-troca-search")).to_have_value("1")
    expect(page.locator("#novo-veiculo-troca-campos")).not_to_be_visible()
    expect(page.locator('input[name="veic_troca_placa"]')).to_be_disabled()
    expect(page.get_by_role("button", name="Carregar mais")).to_have_count(0)
    expect(page.get_by_role("button", name="Cadastrar novo veículo")).to_be_visible()


def _criar_venda_via_wizard(page: Page, live_server_url: str) -> None:
    page.goto(f"{live_server_url}/ui/vendas")
    page.get_by_test_id("vendas-create").click()
    expect(page.get_by_role("dialog", name="Nova venda")).to_be_visible()

    page.get_by_test_id("venda-wizard-client-name").fill("Cliente Venda Setup")
    page.get_by_test_id("venda-wizard-client-document").fill("33344455566")
    page.get_by_test_id("venda-wizard-client-phone").fill("11988888888")
    page.get_by_test_id("venda-wizard-next").click()

    page.get_by_test_id("venda-wizard-vehicle-select").select_option(
        label="ABC1234 — Onix"
    )
    page.get_by_test_id("venda-wizard-next").click()

    page.get_by_test_id("venda-wizard-value").fill("130000")
    page.get_by_test_id("venda-wizard-payment-method").fill("Pix")
    page.get_by_test_id("venda-wizard-next").click()

    page.get_by_test_id("venda-wizard-save").click()
    expect(page.get_by_role("dialog", name="Nova venda")).not_to_be_visible()
    expect(page.get_by_text("Cliente Venda Setup")).to_be_visible()


@pytest.mark.e2e
def test_modal_venda_editar_atualiza_valor(page: Page, live_server_url: str) -> None:
    _login(page, live_server_url)
    _criar_venda_via_wizard(page, live_server_url)

    linha = page.locator("tr", has_text="Cliente Venda Setup")
    linha.get_by_role("button", name="Editar venda").click()

    expect(page.get_by_role("dialog", name="Editar venda")).to_be_visible()
    valor = page.get_by_test_id("venda-edit-value")
    valor.fill("")
    valor.fill("140000")
    page.get_by_test_id("venda-edit-save").click()

    expect(page.get_by_role("dialog", name="Editar venda")).not_to_be_visible()
    expect(page.get_by_role("status")).to_contain_text("Alterações salvas com sucesso")
    expect(page.locator("tr", has_text="Cliente Venda Setup")).to_contain_text(
        "R$ 140.000,00"
    )


@pytest.mark.e2e
def test_modal_venda_fechamento_confirma_rateio(
    page: Page, live_server_url: str
) -> None:
    _login(page, live_server_url)
    _criar_venda_via_wizard(page, live_server_url)

    linha = page.locator("tr", has_text="Cliente Venda Setup")
    linha.get_by_role("button", name="Fechar venda").click()

    dialog = page.get_by_role("dialog")
    expect(dialog).to_be_visible()
    expect(dialog).to_contain_text("Fechamento da venda")

    dialog.locator('input[name="percentual"]').fill("100")
    confirmar = dialog.get_by_role("button", name="Confirmar fechamento")
    expect(confirmar).to_be_enabled()
    confirmar.click()

    # hx-confirm é interceptado por um modal estilizado (base.html), não pelo
    # confirm() nativo do navegador.
    page.get_by_role("alertdialog").get_by_role("button", name="Confirmar").click()

    expect(page.locator("tr", has_text="Cliente Venda Setup")).to_contain_text(
        "Fechada"
    )


def _criar_compra_via_wizard(
    page: Page, live_server_url: str, tmp_path: Path, *, cliente: str, placa: str
) -> None:
    page.goto(f"{live_server_url}/ui/compras")
    page.get_by_test_id("compras-create").click()
    expect(page.get_by_role("dialog", name="Nova compra")).to_be_visible()

    page.get_by_test_id("compra-wizard-client-name").fill(cliente)
    page.get_by_test_id("compra-wizard-client-document").fill("11122233344")
    page.get_by_test_id("compra-wizard-client-phone").fill("11999999999")
    page.get_by_test_id("compra-wizard-client-email").fill("cliente-e2e@example.com")

    page.get_by_test_id("compra-wizard-next").click()
    page.get_by_test_id("compra-wizard-vehicle-plate").fill(placa)
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
    expect(page.get_by_text(cliente)).to_be_visible()


@pytest.mark.e2e
def test_modal_compra_editar_atualiza_valor(
    page: Page, live_server_url: str, tmp_path: Path
) -> None:
    _login(page, live_server_url)
    _criar_compra_via_wizard(
        page,
        live_server_url,
        tmp_path,
        cliente="Cliente Compra Editar",
        placa="EDT1234",
    )

    linha = page.locator("tr", has_text="Cliente Compra Editar")
    linha.get_by_role("button", name="Editar compra").click()

    expect(page.get_by_role("dialog", name="Editar compra")).to_be_visible()
    valor = page.get_by_test_id("compra-edit-value")
    valor.fill("")
    valor.fill("99000")
    page.get_by_test_id("compra-edit-save").click()

    expect(page.get_by_role("dialog", name="Editar compra")).not_to_be_visible()
    expect(page.get_by_role("status")).to_contain_text("Alterações salvas com sucesso")
    expect(page.locator("tr", has_text="Cliente Compra Editar")).to_contain_text(
        "R$ 99.000,00"
    )


@pytest.mark.e2e
def test_modal_compra_comprovantes_upload_e_exclusao(
    page: Page, live_server_url: str, tmp_path: Path
) -> None:
    _login(page, live_server_url)
    _criar_compra_via_wizard(
        page,
        live_server_url,
        tmp_path,
        cliente="Cliente Compra Comprovantes",
        placa="CMP1234",
    )

    linha = page.locator("tr", has_text="Cliente Compra Comprovantes")
    linha.get_by_role("button", name="Comprovantes da compra").click()

    dialog = page.get_by_role("dialog", name="Comprovantes")
    expect(dialog).to_be_visible()
    # o comprovante enviado no wizard já aparece listado aqui
    expect(dialog.get_by_role("button", name="Excluir comprovante")).to_have_count(1)

    novo = tmp_path / "comprovante2.pdf"
    novo.write_bytes(b"%PDF-1.4\n%%EOF\n")
    dialog.get_by_test_id("modal-comprovantes-title-upload-input").set_input_files(novo)
    dialog.get_by_test_id("modal-comprovantes-title-upload-submit").click()

    dialog = page.get_by_role("dialog", name="Comprovantes")
    expect(dialog.get_by_role("button", name="Excluir comprovante")).to_have_count(2)

    dialog.get_by_role("button", name="Excluir comprovante").first.click()
    page.get_by_role("alertdialog").get_by_role("button", name="Confirmar").click()

    dialog = page.get_by_role("dialog", name="Comprovantes")
    expect(dialog.get_by_role("button", name="Excluir comprovante")).to_have_count(1)


@pytest.mark.e2e
def test_modal_custo_veiculo_cria_e_edita_custo(
    page: Page, live_server_url: str
) -> None:
    _login(page, live_server_url)
    page.goto(f"{live_server_url}/ui/custos-veiculos")

    page.get_by_test_id("custos-veiculos-create").click()
    expect(page.get_by_role("dialog", name="Novo custo")).to_be_visible()

    page.get_by_test_id("custo-veiculo-form-vehicle").select_option(
        label="ABC1234 · Onix"
    )
    page.get_by_test_id("custo-veiculo-form-category").fill("Manutenção")
    page.get_by_test_id("custo-veiculo-form-value").fill("450")
    page.get_by_test_id("custo-veiculo-form-save").click()

    expect(page.get_by_role("dialog", name="Novo custo")).not_to_be_visible()
    expect(page.get_by_role("status")).to_contain_text("Alterações salvas com sucesso")
    linha = page.locator("tr", has_text="Manutenção")
    expect(linha).to_contain_text("R$ 450,00")

    linha.get_by_role("button", name="Editar custo").click()
    expect(page.get_by_role("dialog", name="Editar custo")).to_be_visible()
    valor = page.get_by_test_id("custo-veiculo-form-value")
    valor.fill("")
    valor.fill("600")
    page.get_by_test_id("custo-veiculo-form-save").click()

    expect(page.get_by_role("dialog", name="Editar custo")).not_to_be_visible()
    expect(page.locator("tr", has_text="Manutenção")).to_contain_text("R$ 600,00")


@pytest.mark.e2e
def test_modal_investidor_cria_e_edita(page: Page, live_server_url: str) -> None:
    _login(page, live_server_url)
    page.goto(f"{live_server_url}/ui/investidores")

    page.get_by_test_id("investidores-create").click()
    expect(page.get_by_role("dialog", name="Novo — Investidores")).to_be_visible()

    page.get_by_test_id("simples-form-nome").fill("Investidor E2E")
    page.get_by_test_id("simples-form-valor-investido").fill("50000")
    page.get_by_test_id("simples-form-save").click()

    expect(page.get_by_role("dialog", name="Novo — Investidores")).not_to_be_visible()
    expect(page.get_by_role("status")).to_contain_text("Alterações salvas com sucesso")
    linha = page.locator("tr", has_text="Investidor E2E")
    expect(linha).to_be_visible()

    linha.get_by_role("button", name="Editar Investidor E2E").click()
    expect(page.get_by_role("dialog", name="Editar — Investidores")).to_be_visible()
    nome = page.get_by_test_id("simples-form-nome")
    nome.fill("")
    nome.fill("Investidor E2E Editado")
    page.get_by_test_id("simples-form-save").click()

    expect(page.get_by_role("dialog", name="Editar — Investidores")).not_to_be_visible()
    expect(page.locator("tr", has_text="Investidor E2E Editado")).to_be_visible()


@pytest.mark.e2e
def test_modal_lancamento_cria_e_edita(page: Page, live_server_url: str) -> None:
    _login(page, live_server_url)
    page.goto(f"{live_server_url}/ui/investidores")

    linha = page.locator("tr", has_text="Investidor A")
    linha.get_by_role("link", name="Lançamentos de Investidor A").click()
    expect(page).to_have_url(re.compile(r"/ui/investidores/\d+/lancamentos"))

    page.get_by_test_id("lancamentos-create").click()
    expect(page.get_by_role("dialog", name="Novo lançamento")).to_be_visible()

    page.get_by_test_id("lancamento-form-tipo").select_option(label="Aporte")
    page.get_by_test_id("lancamento-form-valor").fill("1000")
    page.get_by_test_id("lancamento-form-descricao").fill("Aporte E2E")
    page.get_by_test_id("lancamento-form-save").click()

    expect(page.get_by_role("dialog", name="Novo lançamento")).not_to_be_visible()
    expect(page.get_by_role("status")).to_contain_text("Alterações salvas com sucesso")
    linha_lanc = page.locator("tr", has_text="Aporte E2E")
    expect(linha_lanc).to_be_visible()

    linha_lanc.get_by_role("button", name="Editar lançamento").click()
    expect(page.get_by_role("dialog", name="Editar lançamento")).to_be_visible()
    valor = page.get_by_test_id("lancamento-form-valor")
    valor.fill("")
    valor.fill("2000")
    page.get_by_test_id("lancamento-form-save").click()

    expect(page.get_by_role("dialog", name="Editar lançamento")).not_to_be_visible()
    expect(page.locator("tr", has_text="Aporte E2E")).to_contain_text("R$ 2.000,00")


@pytest.mark.e2e
def test_modal_perfil_cria_e_edita(page: Page, live_server_url: str) -> None:
    _login(page, live_server_url)
    page.goto(f"{live_server_url}/ui/perfis")

    page.get_by_test_id("perfis-create").click()
    expect(page.get_by_role("dialog", name="Novo perfil")).to_be_visible()

    page.get_by_test_id("perfil-form-nome").fill("Perfil E2E")
    page.get_by_label("Veículos").check()
    page.get_by_test_id("perfil-form-save").click()

    expect(page.get_by_role("dialog", name="Novo perfil")).not_to_be_visible()
    expect(page.get_by_role("status")).to_contain_text("Alterações salvas com sucesso")
    linha = page.locator("tr", has_text="Perfil E2E")
    expect(linha).to_be_visible()

    linha.get_by_role("button", name="Editar Perfil E2E").click()
    expect(page.get_by_role("dialog", name="Editar perfil")).to_be_visible()
    nome = page.get_by_test_id("perfil-form-nome")
    nome.fill("")
    nome.fill("Perfil E2E Editado")
    page.get_by_test_id("perfil-form-save").click()

    expect(page.get_by_role("dialog", name="Editar perfil")).not_to_be_visible()
    expect(page.locator("tr", has_text="Perfil E2E Editado")).to_be_visible()


@pytest.mark.e2e
def test_modal_usuario_cria_e_edita(page: Page, live_server_url: str) -> None:
    _login(page, live_server_url)
    page.goto(f"{live_server_url}/ui/usuarios")

    page.get_by_test_id("usuarios-create").click()
    expect(page.get_by_role("dialog", name="Novo usuário")).to_be_visible()

    page.get_by_test_id("usuario-form-username").fill("usuario.e2e")
    page.get_by_test_id("usuario-form-nome").fill("Usuario E2E")
    page.get_by_test_id("usuario-form-senha").fill("senha12345")
    page.get_by_test_id("usuario-form-save").click()

    expect(page.get_by_role("dialog", name="Novo usuário")).not_to_be_visible()
    expect(page.get_by_role("status")).to_contain_text("Alterações salvas com sucesso")
    linha = page.locator("tr", has_text="usuario.e2e")
    expect(linha).to_be_visible()

    linha.get_by_role("button", name="Editar usuario.e2e").click()
    expect(page.get_by_role("dialog", name="Editar usuário")).to_be_visible()
    nome = page.get_by_test_id("usuario-editar-username")
    nome.fill("")
    nome.fill("usuario.e2e.editado")
    page.get_by_test_id("usuario-editar-save").click()

    expect(page.get_by_role("dialog", name="Editar usuário")).not_to_be_visible()
    expect(page.locator("tr", has_text="usuario.e2e.editado")).to_be_visible()


@pytest.mark.e2e
def test_modal_veiculo_documentos_upload_e_exclusao(
    page: Page, live_server_url: str, tmp_path: Path
) -> None:
    _login(page, live_server_url)
    page.goto(f"{live_server_url}/ui/veiculos")

    linha = page.locator("tr", has_text="Onix")
    linha.get_by_role("button", name="Documento do veículo Onix").click()

    dialog = page.get_by_role("dialog", name="Documento do Veículo")
    expect(dialog).to_be_visible()
    expect(dialog.get_by_role("button", name="Excluir documento")).to_have_count(0)

    doc = tmp_path / "documento.pdf"
    doc.write_bytes(b"%PDF-1.4\n%%EOF\n")
    dialog.get_by_test_id("modal-documentos-title-upload-input").set_input_files(doc)
    dialog.get_by_test_id("modal-documentos-title-upload-submit").click()

    dialog = page.get_by_role("dialog", name="Documento do Veículo")
    expect(dialog.get_by_role("button", name="Excluir documento")).to_have_count(1)

    dialog.get_by_role("button", name="Excluir documento").click()
    page.get_by_role("alertdialog").get_by_role("button", name="Confirmar").click()

    dialog = page.get_by_role("dialog", name="Documento do Veículo")
    expect(dialog.get_by_role("button", name="Excluir documento")).to_have_count(0)


@pytest.mark.e2e
def test_modal_veiculos_vinculados_cliente_sem_historico(
    page: Page, live_server_url: str
) -> None:
    _login(page, live_server_url)
    page.goto(f"{live_server_url}/ui/clientes/todos")

    page.get_by_test_id("clientes-create").click()
    page.get_by_test_id("cliente-form-name").fill("Cliente Sem Veiculos")
    page.get_by_test_id("cliente-form-document").fill("55566677788")
    page.get_by_test_id("cliente-form-type").select_option(label="Pessoa Fisica")
    page.get_by_test_id("cliente-form-save").click()
    expect(page.get_by_text("Cliente Sem Veiculos")).to_be_visible()

    linha = page.locator("tr", has_text="Cliente Sem Veiculos")
    linha.get_by_role("button", name="Veículos de Cliente Sem Veiculos").click()

    dialog = page.get_by_role("dialog", name="Veículos")
    expect(dialog).to_be_visible()
    expect(dialog).to_contain_text("Nenhum veículo")


@pytest.mark.e2e
def test_modal_auditoria_detalhe_mostra_registro(
    page: Page, live_server_url: str
) -> None:
    _login(page, live_server_url)

    # gera um registro de auditoria criando um cliente
    page.goto(f"{live_server_url}/ui/clientes/todos")
    page.get_by_test_id("clientes-create").click()
    page.get_by_test_id("cliente-form-name").fill("Cliente Auditoria")
    page.get_by_test_id("cliente-form-document").fill("66677788899")
    page.get_by_test_id("cliente-form-type").select_option(label="Pessoa Fisica")
    page.get_by_test_id("cliente-form-save").click()
    expect(page.get_by_text("Cliente Auditoria")).to_be_visible()

    page.goto(f"{live_server_url}/ui/auditoria")
    details_button = page.get_by_role(
        "button", name=re.compile("Ver detalhes do registro")
    )
    details_button.first.click()

    dialog = page.get_by_role("dialog")
    expect(dialog).to_be_visible()
    expect(dialog).to_contain_text("Registro #")


def _login(page: Page, live_server_url: str) -> None:
    page.goto(f"{live_server_url}/ui/login")
    page.get_by_test_id("login-username").fill("admin")
    page.get_by_test_id("login-password").fill("senha")
    page.get_by_test_id("login-submit").click()
    expect(page).to_have_url(f"{live_server_url}/ui/veiculos")
