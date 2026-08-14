"""Mensagens de validação da HTMX UI: campo nomeado e motivo concreto."""

import pytest
from pydantic import BaseModel, ValidationError, field_validator

from xtreme_system.api.crud_ui.responses import (
    validation_error_detail,
    validation_error_field,
)
from xtreme_system.cliente.core import ClienteCreate
from xtreme_system.venda.core import VendaCreate


def test_venda_pagamento_pendente_sem_valor_nomeia_o_campo() -> None:
    with pytest.raises(ValidationError) as exc_info:
        VendaCreate.model_validate(
            {
                "cliente_id": 1,
                "veiculo_id": 1,
                "valor_venda": "40000",
                "forma_pagamento": "a_vista",
                "pagamento_pendente": True,
                "datas_pagamento": "10/08/2026",
            }
        )
    assert validation_error_field(exc_info.value) == "valor_pendente"
    assert validation_error_detail(exc_info.value) == (
        "Valor pendente: informe um valor pendente maior que zero."
    )


def test_venda_entrada_maior_que_valor_nomeia_o_campo() -> None:
    with pytest.raises(ValidationError) as exc_info:
        VendaCreate.model_validate(
            {
                "cliente_id": 1,
                "veiculo_id": 1,
                "valor_venda": "10000",
                "valor_entrada": "20000",
                "forma_pagamento": "a_vista",
            }
        )
    assert validation_error_field(exc_info.value) == "valor_entrada"
    assert validation_error_detail(exc_info.value) == (
        "Entrada: não pode ser maior que o valor da venda."
    )


def test_venda_datas_sem_pagamento_pendente_nomeia_o_campo() -> None:
    with pytest.raises(ValidationError) as exc_info:
        VendaCreate.model_validate(
            {
                "cliente_id": 1,
                "veiculo_id": 1,
                "valor_venda": "40000",
                "forma_pagamento": "a_vista",
                "datas_pagamento": "10/08",
            }
        )
    assert validation_error_field(exc_info.value) == "pagamento_pendente"
    assert validation_error_detail(exc_info.value) == (
        "Pagamento pendente: marque pagamento pendente para informar as datas."
    )


def test_cliente_documento_curto_nomeia_o_campo() -> None:
    with pytest.raises(ValidationError) as exc_info:
        ClienteCreate.model_validate(
            {
                "nome": "Ana",
                "documento": "123",
                "tipo": "pessoa_fisica",
                "telefone": "11999999999",
            }
        )
    assert validation_error_field(exc_info.value) == "documento"
    assert "Campo informado" not in validation_error_detail(exc_info.value)
    assert validation_error_detail(exc_info.value) == (
        "Documento: CPF deve ter 11 dígitos (pessoa física) "
        "ou CNPJ 14 dígitos (pessoa jurídica)."
    )


def test_cliente_email_invalido_usa_motivo_especifico() -> None:
    with pytest.raises(ValidationError) as exc_info:
        ClienteCreate.model_validate(
            {
                "nome": "Ana",
                "documento": "12345678901",
                "tipo": "pessoa_fisica",
                "email": "nao-e-email",
            }
        )
    assert validation_error_field(exc_info.value) == "email"
    assert validation_error_detail(exc_info.value) == (
        "E-mail: informe um e-mail válido."
    )


def test_campo_sem_rotulo_conhecido_usa_o_nome_do_schema() -> None:
    class Amostra(BaseModel):
        campo_sem_rotulo: str

        @field_validator("campo_sem_rotulo")
        @classmethod
        def _rejeitar(cls, value: str) -> str:
            _ = cls
            if value:
                raise ValueError("valor rejeitado")
            return value

    with pytest.raises(ValidationError) as exc_info:
        Amostra.model_validate({"campo_sem_rotulo": "x"})
    assert validation_error_field(exc_info.value) == "campo_sem_rotulo"
    assert validation_error_detail(exc_info.value) == (
        "Campo sem rotulo: valor rejeitado."
    )
