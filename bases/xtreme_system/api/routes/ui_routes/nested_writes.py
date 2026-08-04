"""Helpers for nested entities created by UI form handlers."""

from collections.abc import Callable
from dataclasses import dataclass, field

import structlog
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

logger = structlog.get_logger(__name__)


@dataclass
class NestedWrites:
    """Track nested rows created during one form preparation attempt."""

    pending: list[object] = field(default_factory=list)

    def add(self, data: object | None) -> None:
        if data is not None:
            self.pending.append(data)

    def rollback(self, session: Session) -> None:
        rollback_se_criou_aninhados(session, *self.pending)


def criar_aninhado_ou_resposta_conflito[EntityT, CreateDataT](
    session: Session,
    data: CreateDataT | None,
    create_fn: Callable[[Session, CreateDataT, int | None], EntityT],
    actor_id: int | None,
    nested_writes: NestedWrites | None = None,
) -> tuple[EntityT | None, bool]:
    if data is None:
        return None, False
    nested_writes = nested_writes or NestedWrites()
    nested_writes.add(data)
    try:
        return create_fn(session, data, actor_id), False
    except IntegrityError:
        nested_writes.rollback(session)
        return None, True


def rollback_se_criou_aninhados(
    session: Session, *dados_aninhados: object | None
) -> None:
    if any(dado is not None for dado in dados_aninhados):
        logger.warning("nested_write_rolled_back")
        session.rollback()
