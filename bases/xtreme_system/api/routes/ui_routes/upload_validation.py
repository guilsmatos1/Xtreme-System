"""Validation of files submitted through UI forms."""

from pathlib import Path

from fastapi import UploadFile

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
    " .png".strip(): b"\x89\x50\x4e\x47\x0d\x0a\x1a\x0a",
    ".webp": b"RIFF",
    ".pdf": b"%PDF",
}


def validar_uploads(arquivos: list[UploadFile]) -> str | None:
    """Return the first invalid-file message, or ``None`` for a valid batch."""
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
                "Assinatura do arquivo não confere com a extensão declarada: "
                f"{arq.filename}"
            )
    return None
