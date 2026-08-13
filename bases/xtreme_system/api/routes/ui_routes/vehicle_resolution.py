"""Shared vehicle resolution helpers for UI forms."""

from typing import Any

from pydantic import ValidationError
from sqlalchemy.orm import Session

from xtreme_system.api.crud_ui.responses import validation_error_detail
from xtreme_system.veiculo import core as veiculo


def resolver_veiculo_inline(
    session: Session,
    form: Any,
    *,
    prefix: str,
    tipo_entrada: Any,
    preco: Any,
    required: bool,
    error_label: str,
) -> tuple[veiculo.Veiculo | None, veiculo.VeiculoCreate | None, str | None]:
    """Resolve or parse a vehicle entered inline in a UI form."""
    placa = str(form.get(f"{prefix}placa") or "").strip().upper()
    if not placa:
        if required:
            return None, None, f"Informe a placa {error_label}"
        return None, None, None
    if veiculo.get_by_placa(session, placa):
        return None, None, "Placa já cadastrada — selecione o veículo na lista"

    try:
        novo_veiculo_data = veiculo.VeiculoCreate.model_validate(
            {
                "tipo": form.get(f"{prefix}tipo"),
                "tipo_entrada": tipo_entrada,
                "placa": placa,
                "modelo": str(form.get(f"{prefix}modelo") or "").strip(),
                "marca": str(form.get(f"{prefix}marca") or "").strip() or None,
                "cor": str(form.get(f"{prefix}cor") or "").strip(),
                "ano": form.get(f"{prefix}ano") or 0,
                "km": str(form.get(f"{prefix}km") or "").strip() or None,
                "chassi": str(form.get(f"{prefix}chassi") or "").strip() or None,
                "renavam": str(form.get(f"{prefix}renavam") or "").strip() or None,
                "preco": preco,
                "proprietario_atual": str(
                    form.get(f"{prefix}proprietario_atual") or ""
                ).strip()
                or None,
                "proprietario_documento": str(
                    form.get(f"{prefix}proprietario_documento") or ""
                ).strip()
                or None,
                "investidor_id": form.get(f"{prefix}investidor_id") or 0,
            }
        )
    except ValidationError as exc:
        return None, None, validation_error_detail(exc)
    return None, novo_veiculo_data, None
