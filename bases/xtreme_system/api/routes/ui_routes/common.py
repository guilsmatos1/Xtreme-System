"""Shared helpers for HTMX route modules."""

import contextlib
from pathlib import Path

from fastapi import UploadFile

from xtreme_system.api.setup import _ui_dir


def _uploads_dir(veiculo_id: int) -> Path:
    return _ui_dir / "static" / "uploads" / "veiculos" / str(veiculo_id)


def _uploads_cliente_dir(cliente_id: int) -> Path:
    return _ui_dir / "static" / "uploads" / "clientes" / str(cliente_id) / "documentos"


def _uploads_procuracao_dir(veiculo_id: int) -> Path:
    return _uploads_dir(veiculo_id) / "procuracao"


def _uploads_compra_dir(compra_id: int) -> Path:
    return _ui_dir / "static" / "uploads" / "compras" / str(compra_id) / "comprovantes"


def _uploads_contrato_venda_dir(venda_id: int) -> Path:
    return _ui_dir / "static" / "uploads" / "vendas" / str(venda_id) / "contrato"


_EXTENSOES_PERMITIDAS = {".jpg", ".jpeg", ".png", ".webp", ".pdf"}
_MAX_POR_ARQUIVO = 5 * 1024 * 1024
_TIPO_POR_EXTENSAO = {
    ".jpg": {"image/jpeg", "image/jpg"},
    ".jpeg": {"image/jpeg", "image/jpg"},
    ".png": {"image/png"},
    ".webp": {"image/webp"},
    ".pdf": {"application/pdf"},
}
_MAGIC_BYTES: dict[str, bytes] = {
    ".jpg": b"\xff\xd8\xff",
    ".jpeg": b"\xff\xd8\xff",
    ".png": b"\x89\x50\x4e\x47\x0d\x0a\x1a\x0a",
    ".webp": b"RIFF",
    ".pdf": b"%PDF",
}


def _validar_uploads(arquivos: list[UploadFile]) -> str | None:
    """Retorna mensagem de erro do primeiro arquivo inválido, ou None.

    Lote inteiro é rejeitado no primeiro erro — nenhum arquivo é salvo.
    """
    for arq in arquivos:
        if not arq.filename:
            continue
        ext = Path(arq.filename).suffix.lower()
        if ext not in _EXTENSOES_PERMITIDAS:
            exts = ", ".join(sorted(_EXTENSOES_PERMITIDAS))
            return f"Tipo não permitido: {arq.filename} (aceitos: {exts})"
        ct = (arq.content_type or "").lower()
        if ct and ct not in _TIPO_POR_EXTENSAO[ext]:
            return f"Conteúdo não corresponde à extensão: {arq.filename}"
        tam = arq.size
        if tam is None:
            arq.file.seek(0, 2)
            tam = arq.file.tell()
            arq.file.seek(0)
        if tam > _MAX_POR_ARQUIVO:
            return f"{arq.filename} excede 5 MB ({tam // 1024 // 1024} MB)"
        assinatura = _MAGIC_BYTES[ext]
        prefixo = arq.file.read(len(assinatura))
        arq.file.seek(0)
        if prefixo != assinatura:
            return (
                f"Assinatura do arquivo não confere com a extensão "
                f"declarada: {arq.filename}"
            )
    return None


def _uploaded_file_path(url: str) -> Path | None:
    if not url.startswith("/static/uploads/"):
        return None
    candidate = (_ui_dir / url.lstrip("/")).resolve()
    uploads_root = (_ui_dir / "static" / "uploads").resolve()
    if not candidate.is_relative_to(uploads_root):
        return None
    return candidate


def _remover_upload(path: Path) -> None:
    with contextlib.suppress(FileNotFoundError):
        path.unlink()
