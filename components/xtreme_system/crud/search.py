"""Utilitários para busca textual em consultas SQLAlchemy."""

from collections.abc import Mapping, Sequence
from typing import Any

from sqlalchemy import String, cast, or_
from sqlalchemy.orm import Query

SearchColumn = Any


def apply_text_search[EntityT](
    query: Query[EntityT],
    term: str,
    *,
    columns_map: Mapping[str, SearchColumn],
    default_columns: Sequence[SearchColumn],
    column: str | None = None,
) -> Query[EntityT]:
    pattern = f"%{term}%"

    if column and column in columns_map:
        return query.where(cast(columns_map[column], String).ilike(pattern))

    return query.where(
        or_(*(cast(col, String).ilike(pattern) for col in default_columns))
    )
