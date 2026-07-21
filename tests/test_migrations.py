import os

import pytest
from alembic.autogenerate import compare_metadata
from alembic.migration import MigrationContext

from tests.database import create_test_engine
from xtreme_system.database.core import Base


@pytest.mark.skipif(
    not os.environ.get("TEST_DATABASE_URL"),
    reason="migration drift check requires PostgreSQL",
)
def test_alembic_head_matches_sqlalchemy_metadata() -> None:
    engine = create_test_engine()
    try:
        with engine.connect() as connection:
            context = MigrationContext.configure(
                connection,
                opts={
                    "compare_server_default": True,
                    "compare_type": True,
                    "target_metadata": Base.metadata,
                },
            )

            assert compare_metadata(context, Base.metadata) == []
    finally:
        engine.dispose()
