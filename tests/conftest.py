from collections.abc import Iterator

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker

from xtreme_system.database.core import Base


@pytest.fixture
def db_session() -> Iterator[Session]:
    """Sessão isolada em SQLite in-memory com o schema do Base criado."""
    engine = create_engine("sqlite://", future=True)
    Base.metadata.create_all(engine)
    maker = sessionmaker(bind=engine, autoflush=False, expire_on_commit=False)
    with maker() as session:
        yield session
    engine.dispose()
