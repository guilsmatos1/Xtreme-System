from unittest.mock import Mock

import pytest
from fastapi import HTTPException
from sqlalchemy.exc import IntegrityError

from xtreme_system.api import crud_writes


def test_safe_write_logs_integrity_error_and_preserves_conflict_response() -> None:
    logger = Mock()
    original_logger = crud_writes.logger
    crud_writes.logger = logger
    try:
        with pytest.raises(HTTPException) as raised:
            crud_writes.safe_write(
                lambda: (_ for _ in ()).throw(
                    IntegrityError("INSERT", {}, RuntimeError("duplicate plate"))
                ),
                conflict_msg="Venda já existe",
            )
    finally:
        crud_writes.logger = original_logger

    assert raised.value.status_code == 409
    assert raised.value.detail == "Venda já existe"
    logger.warning.assert_called_once_with(
        "write_conflict",
        conflict_msg="Venda já existe",
        erro="duplicate plate",
    )
