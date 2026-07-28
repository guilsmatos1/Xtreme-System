"""Authorization policy for files served from /static/uploads."""

from dataclasses import dataclass
from typing import Any

from sqlalchemy.orm import Session

from xtreme_system.database.core import Base
from xtreme_system.documento_contrato_venda.core import DocumentoContratoVenda
from xtreme_system.documento_procuracao.core import DocumentoProcuracao
from xtreme_system.documento_veiculo.core import DocumentoVeiculo
from xtreme_system.empresa.core import EmpresaConfig
from xtreme_system.imagem_comprovante_compra.core import ImagemComprovanteCompra
from xtreme_system.imagem_documento_cliente.core import ImagemDocumentoCliente
from xtreme_system.imagem_veiculo.core import ImagemVeiculo
from xtreme_system.perfil import core as perfil
from xtreme_system.usuario import core as usuario


@dataclass(frozen=True)
class UploadRule:
    prefix: str
    subdir: str | None
    pagina: str | None
    operacao: str | None
    model: type[Base]
    min_parts: int
    url_field: str = "url"


UPLOAD_RULES = [
    UploadRule("empresa", None, None, None, EmpresaConfig, 2, "logo_url"),
    UploadRule("clientes", "documentos", "clientes", None, ImagemDocumentoCliente, 4),
    UploadRule(
        "compras",
        "comprovantes",
        "compras",
        "abrir_comprovante",
        ImagemComprovanteCompra,
        4,
    ),
    UploadRule(
        "vendas",
        "contrato",
        "vendas",
        "baixar_contrato",
        DocumentoContratoVenda,
        4,
    ),
    UploadRule(
        "veiculos",
        "documentos",
        "veiculos",
        "upload_documento",
        DocumentoVeiculo,
        4,
    ),
    UploadRule(
        "veiculos",
        "procuracao",
        "veiculos",
        "abrir_procuracao",
        DocumentoProcuracao,
        4,
    ),
    UploadRule("veiculos", None, "veiculos", "abrir_imagens", ImagemVeiculo, 3),
]


def _rule_matches(parts: list[str], rule: UploadRule) -> bool:
    return (
        len(parts) >= rule.min_parts
        and parts[0] == rule.prefix
        and (rule.subdir is None or parts[2] == rule.subdir)
    )


def pode_acessar_upload(session: Session, user: Any, url: str) -> bool:
    """Return whether ``user`` may access the persisted upload at ``url``."""
    if usuario.is_admin(user):
        return True

    parts = url.removeprefix("/static/uploads/").split("/")
    for rule in UPLOAD_RULES:
        if not _rule_matches(parts, rule):
            continue
        if rule.operacao is not None:
            autorizado = perfil.pode_operacao(user, rule.pagina or "", rule.operacao)
        elif rule.pagina is not None:
            autorizado = perfil.pode_acessar(user, rule.pagina)
        else:
            autorizado = True
        if not autorizado:
            return False
        return (
            session.query(rule.model).filter_by(**{rule.url_field: url}).first()
            is not None
        )
    return False
