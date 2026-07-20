"""Perfil de permissões: quais páginas da UI um perfil de usuário pode acessar."""

from typing import Any

from pydantic import BaseModel, ConfigDict
from sqlalchemy import JSON
from sqlalchemy.orm import Mapped, Session, mapped_column

from xtreme_system.crud import core as crud
from xtreme_system.database.core import Base

# Única fonte da verdade: chave usada na URL (/ui/{chave}) e no menu.
PAGINAS: list[tuple[str, str]] = [
    ("veiculos", "Veículos"),
    ("investidores", "Investidores"),
    ("clientes", "Clientes"),
    ("compras", "Compras"),
    ("custos-veiculos", "Custos"),
    ("vendas", "Vendas"),
]
PAGINAS_VALIDAS = {chave for chave, _ in PAGINAS}

# Campos sensíveis e operações que podem ser restringidos por perfil, por página.
CAMPOS_PROTEGIDOS: dict[str, list[tuple[str, str]]] = {
    "veiculos": [
        ("modelo", "Modelo"),
        ("placa", "Placa"),
        ("tipo", "Tipo"),
        ("ano", "Ano"),
        ("km", "KM"),
        ("status", "Estado"),
        ("preco", "Preço de Custo"),
        ("tipo_entrada", "Tipo de Entrada"),
        ("investidor", "Investidor"),
        ("procuracao", "Procurador"),
        ("revisao", "Revisão"),
        ("debitos", "Débitos"),
        ("tempo_estoque", "Tempo de Estoque"),
    ],
    "compras": [
        ("data_compra", "Data da Compra"),
        ("cliente", "Cliente"),
        ("documento_cliente", "Documento do Cliente"),
        ("status", "Estado"),
        ("placa", "Placa"),
        ("veiculo", "Veículo"),
        ("valor_compra", "Valor da Compra"),
        ("debitos", "Débitos"),
        ("observacoes", "Observações"),
    ],
    "custos-veiculos": [
        ("valor", "Valor"),
    ],
    "vendas": [
        ("cliente", "Cliente"),
        ("veiculo", "Veículo"),
        ("data_venda", "Data da Venda"),
        ("valor_venda", "Valor da Venda"),
        ("valor_entrada", "Entrada"),
        ("debitos", "Débitos"),
        ("km", "KM"),
        ("veiculo_troca", "Veículo da Troca"),
        ("valor_diferenca", "Valor da Diferença"),
        ("pagamento_pendente", "Pagamento Pendente"),
        ("valor_pendente", "Valor Pendente"),
        ("datas_pagamento", "Datas de Pagamento"),
        ("forma_pagamento", "Forma de Pagamento"),
        ("parcelas", "Parcelas"),
        ("status", "Status"),
        ("observacoes", "Observações"),
        ("lucro", "Lucro Líquido (fechamento)"),
        ("participacao", "Participação por Investidor (fechamento)"),
    ],
}
OPERACOES: dict[str, list[tuple[str, str]]] = {
    "veiculos": [
        ("editar", "Editar"),
        ("excluir", "Excluir"),
        ("abrir_cliente_vendedor", "Abrir cliente vendedor"),
        ("upload_documento", "Upload de documento do veículo"),
        ("abrir_imagens", "Abrir imagens do veículo"),
        ("enviar_imagens", "Enviar imagens"),
        ("excluir_imagens", "Excluir imagens"),
        ("abrir_procuracao", "Abrir procuração"),
        ("enviar_procuracao", "Enviar documentos de procuração"),
        ("excluir_procuracao", "Excluir documentos de procuração"),
    ],
    "investidores": [
        ("editar", "Editar"),
        ("excluir", "Excluir"),
    ],
    "clientes": [
        ("cadastrar", "Cadastrar"),
        ("editar", "Editar"),
        ("excluir", "Excluir"),
        ("excluir_documento", "Excluir documento"),
    ],
    "compras": [
        ("cadastrar", "Cadastrar"),
        ("editar", "Editar"),
        ("excluir", "Excluir"),
        ("abrir_comprovante", "Abrir comprovantes"),
        ("enviar_comprovante", "Enviar comprovantes"),
        ("excluir_comprovante", "Excluir comprovante"),
    ],
    "custos-veiculos": [
        ("editar", "Editar"),
        ("excluir", "Excluir"),
    ],
    "vendas": [
        ("cadastrar", "Cadastrar"),
        ("editar", "Editar"),
        ("excluir", "Excluir"),
        ("baixar_contrato", "Baixar contrato"),
        ("fechar", "Fechar venda"),
        ("ver_fechamento", "Ver fechamento"),
    ],
}


class Perfil(Base):
    __tablename__ = "perfil"

    id: Mapped[int] = mapped_column(primary_key=True)
    nome: Mapped[str] = mapped_column(unique=True, index=True)
    paginas: Mapped[list[str]] = mapped_column(JSON, default=list)
    # Por página: campos_ocultos (denylist) e operacoes (allowlist) permitidas.
    restricoes: Mapped[dict[str, Any]] = mapped_column(JSON, default=dict)


class PerfilCreate(BaseModel):
    nome: str
    paginas: list[str] = []
    restricoes: dict[str, Any] = {}


class PerfilUpdate(BaseModel):
    nome: str | None = None
    paginas: list[str] | None = None
    restricoes: dict[str, Any] | None = None


class PerfilRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    nome: str
    paginas: list[str]
    restricoes: dict[str, Any]


def list_all(session: Session) -> list[Perfil]:
    return crud.list_all(session, Perfil)


def get(session: Session, perfil_id: int) -> Perfil | None:
    return crud.get(session, Perfil, perfil_id)


def create(session: Session, data: PerfilCreate, actor_id: int | None = None) -> Perfil:
    return crud.create(session, Perfil, data, actor_id)


def update(
    session: Session, obj: Perfil, data: PerfilUpdate, actor_id: int | None = None
) -> Perfil:
    return crud.update(session, obj, data, actor_id)


def delete(session: Session, obj: Perfil, actor_id: int | None = None) -> None:
    from xtreme_system.usuario.core import Usuario  # noqa: PLC0415 (import circular)

    for user in session.query(Usuario).filter_by(perfil_id=obj.id):
        user.perfil_id = None
    session.flush()
    crud.delete(session, obj, actor_id)


def pagina_da_rota(path: str) -> str | None:
    if not path.startswith("/ui/"):
        return None
    segmento = path.removeprefix("/ui/").split("/", 1)[0]
    return segmento if segmento in PAGINAS_VALIDAS else None


def pode_acessar(user: Any, pagina: str) -> bool:
    from xtreme_system.usuario.core import is_admin  # noqa: PLC0415

    if is_admin(user):
        return True
    return bool(user.perfil and pagina in user.perfil.paginas)


def pode_ver_campo(user: Any, pagina: str, campo: str) -> bool:
    from xtreme_system.usuario.core import is_admin  # noqa: PLC0415

    if is_admin(user):
        return True
    if not user.perfil:
        return False
    ocultos = (user.perfil.restricoes or {}).get(pagina, {}).get("campos_ocultos", [])
    return campo not in ocultos


def pode_operacao(user: Any, pagina: str, operacao: str) -> bool:
    from xtreme_system.usuario.core import is_admin  # noqa: PLC0415

    if is_admin(user):
        return True
    if not user.perfil:
        return False
    permitidas = (user.perfil.restricoes or {}).get(pagina, {}).get("operacoes", [])
    return operacao in permitidas
