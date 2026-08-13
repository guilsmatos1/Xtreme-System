from collections.abc import Callable

import pytest
from fastapi.testclient import TestClient
from pydantic import ValidationError

from xtreme_system.cliente import core as cliente
from xtreme_system.usuario import core as usuario


def _token(client: TestClient) -> str:
    resp = client.post("/login", data={"username": "admin", "password": "senha"})
    assert resp.status_code == 200
    return str(resp.json()["access_token"])


def test_cliente_create_normaliza_dados_essenciais() -> None:
    data = cliente.ClienteCreate(
        nome="  Ana Cliente  ",
        documento="123.456.789-01",
        tipo=cliente.TipoCliente.pessoa_fisica,
        email="  ANA@EXEMPLO.COM  ",
        telefone="(11) 99999-0000",
        telefone2="(11) 98888-0000",
        endereco="  Rua A  ",
        bairro="  Centro  ",
        cidade="  São Paulo  ",
        estado=" sp ",
        cep="01001-000",
        profissao="  lojista  ",
    )

    assert data.nome == "ANA CLIENTE"
    assert data.documento == "12345678901"
    assert data.email == "ANA@EXEMPLO.COM"
    assert data.telefone == "11999990000"
    assert data.telefone2 == "11988880000"
    assert data.endereco == "RUA A"
    assert data.bairro == "CENTRO"
    assert data.cidade == "SÃO PAULO"
    assert data.estado == "SP"
    assert data.cep == "01001000"
    assert data.profissao == "lojista"


@pytest.mark.parametrize(
    ("tipo", "documento"),
    [
        (cliente.TipoCliente.pessoa_fisica, "1234567890"),
        (cliente.TipoCliente.pessoa_juridica, "1234567890123"),
    ],
)
def test_cliente_create_valida_documento_por_tipo(
    tipo: cliente.TipoCliente, documento: str
) -> None:
    with pytest.raises(ValidationError):
        cliente.ClienteCreate(nome="Ana", documento=documento, tipo=tipo)


def test_cliente_create_valida_email_estado_e_cep() -> None:
    with pytest.raises(ValidationError):
        cliente.ClienteCreate(
            nome="Ana",
            documento="12345678901",
            tipo=cliente.TipoCliente.pessoa_fisica,
            email="ana",
        )
    with pytest.raises(ValidationError):
        cliente.ClienteCreate(
            nome="Ana",
            documento="12345678901",
            tipo=cliente.TipoCliente.pessoa_fisica,
            estado="Sao Paulo",
        )
    with pytest.raises(ValidationError):
        cliente.ClienteCreate(
            nome="Ana",
            documento="12345678901",
            tipo=cliente.TipoCliente.pessoa_fisica,
            cep="123",
        )


def test_api_clientes_persiste_dados_normalizados(
    make_client: Callable[..., TestClient],
) -> None:
    client = make_client(usuarios=[("admin", usuario.Papel.admin)])
    headers = {"Authorization": f"Bearer {_token(client)}"}

    resp = client.post(
        "/clientes",
        json={
            "nome": "  Ana Cliente  ",
            "documento": "123.456.789-01",
            "tipo": "pessoa_fisica",
            "email": "  ANA@EXEMPLO.COM  ",
            "telefone": "(11) 99999-0000",
            "telefone2": "(11) 98888-0000",
            "estado": "sp",
            "cep": "01001-000",
        },
        headers=headers,
    )

    assert resp.status_code == 201, resp.text
    assert resp.json() == {
        "id": resp.json()["id"],
        "nome": "ANA CLIENTE",
        "documento": "12345678901",
        "tipo": "pessoa_fisica",
        "email": "ANA@EXEMPLO.COM",
        "telefone": "11999990000",
        "telefone2": "11988880000",
        "endereco": None,
        "bairro": None,
        "cidade": None,
        "estado": "SP",
        "cep": "01001000",
        "profissao": None,
    }


def test_api_clientes_rejeita_documento_invalido(
    make_client: Callable[..., TestClient],
) -> None:
    client = make_client(usuarios=[("admin", usuario.Papel.admin)])
    headers = {"Authorization": f"Bearer {_token(client)}"}

    resp = client.post(
        "/clientes",
        json={
            "nome": "Ana Cliente",
            "documento": "123",
            "tipo": "pessoa_fisica",
        },
        headers=headers,
    )

    assert resp.status_code == 422


def test_formatar_documento_cpf_e_cnpj() -> None:
    assert cliente.formatar_documento("12345678901") == "123.456.789-01"
    assert cliente.formatar_documento("12345678000102") == "12.345.678/0001-02"
    assert cliente.formatar_documento(None) == "-"
    assert cliente.formatar_documento("123") == "123"


def test_formatar_telefone_celular_e_fixo() -> None:
    assert cliente.formatar_telefone("11999990000") == "(11) 99999-0000"
    assert cliente.formatar_telefone("1140040000") == "(11) 4004-0000"
    assert cliente.formatar_telefone(None) == "-"
    assert cliente.formatar_telefone("123") == "123"
