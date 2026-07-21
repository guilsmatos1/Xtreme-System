"""Rate limiting helpers for login attempts."""

from datetime import UTC, datetime, timedelta

from sqlalchemy import (
    Column,
    Connection,
    DateTime,
    Integer,
    String,
    Table,
    and_,
    select,
    update,
)
from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.dialects.sqlite import insert as sqlite_insert
from sqlalchemy.orm import Session

from xtreme_system.database.core import Base

login_attempt_rate_limit = Table(
    "login_attempt_rate_limit",
    Base.metadata,
    Column("scope", String(32), primary_key=True),
    Column("bucket", String(255), primary_key=True),
    Column("window_started_at", DateTime(), nullable=False),
    Column("hit_count", Integer, nullable=False),
)


def _utcnow() -> datetime:
    return datetime.now(UTC).replace(tzinfo=None)


def allow_login_attempt(
    session: Session,
    bucket: str,
    limit: int,
    window_seconds: float,
) -> float | None:
    now = _utcnow()
    window = timedelta(seconds=window_seconds)
    cutoff = now - window
    table = login_attempt_rate_limit
    predicate = and_(table.c.scope == "login", table.c.bucket == bucket)

    bind = session.get_bind()
    is_sqlite = bind.dialect.name == "sqlite"

    def _try_claim(connection: Connection) -> bool:
        updated = connection.execute(
            update(table)
            .where(predicate)
            .where(table.c.window_started_at > cutoff)
            .where(table.c.hit_count < limit)
            .values(hit_count=table.c.hit_count + 1)
        ).rowcount
        if updated:
            return True

        reset = connection.execute(
            update(table)
            .where(predicate)
            .where(table.c.window_started_at <= cutoff)
            .values(window_started_at=now, hit_count=1)
        ).rowcount
        if reset:
            return True

        # Dialect-aware insert: SQLite vs PostgreSQL handle conflicts differently
        if is_sqlite:
            # SQLite: use OR IGNORE and check rowcount (reliable for OR IGNORE)
            inserted = connection.execute(
                sqlite_insert(table)
                .prefix_with("OR IGNORE")
                .values(
                    scope="login",
                    bucket=bucket,
                    window_started_at=now,
                    hit_count=1,
                )
            ).rowcount
            return bool(inserted)
        # PostgreSQL: use ON CONFLICT DO NOTHING and check rowcount
        inserted = connection.execute(
            pg_insert(table)
            .values(
                scope="login",
                bucket=bucket,
                window_started_at=now,
                hit_count=1,
            )
            .on_conflict_do_nothing(index_elements=["scope", "bucket"])
        ).rowcount
        return bool(inserted)

    for _ in range(2):
        if isinstance(bind, Connection):
            with bind.begin():
                claimed = _try_claim(bind)
        else:
            with bind.begin() as connection:
                claimed = _try_claim(connection)
        if claimed:
            return None

    if isinstance(bind, Connection):
        row = (
            bind.execute(
                select(table.c.window_started_at, table.c.hit_count).where(predicate)
            )
            .mappings()
            .one_or_none()
        )
    else:
        with bind.begin() as connection:
            row = (
                connection.execute(
                    select(table.c.window_started_at, table.c.hit_count).where(
                        predicate
                    )
                )
                .mappings()
                .one_or_none()
            )
    if row is None:
        return 0.0

    window_started_at: datetime = row["window_started_at"]
    retry_after = (window_started_at + window - now).total_seconds()
    return max(retry_after, 0.0)
