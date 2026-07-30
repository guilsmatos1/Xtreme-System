"""Helpers for nested entities created by UI form handlers."""

from collections.abc import Callable

from fastapi.responses import HTMLResponse
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from xtreme_system.api.crud_ui.responses import rollback_integrity_error_response


def criar_aninhado_ou_resposta_conflito[EntityT, CreateDataT](
    session: Session,
    data: CreateDataT | None,
    create_fn: Callable[[Session, CreateDataT, int | None], EntityT],
    actor_id: int | None,
    build_conflict_response: Callable[[], HTMLResponse],
) -> tuple[EntityT | None, HTMLResponse | None]:
    if data is None:
        return None, None
    try:
        return create_fn(session, data, actor_id), None
    except IntegrityError:
        return None, rollback_integrity_error_response(session, build_conflict_response)


def rollback_se_criou_aninhados(
    session: Session, *dados_aninhados: object | None
) -> None:
    if any(dado is not None for dado in dados_aninhados):
        session.rollback()
