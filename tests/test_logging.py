import logging

import pytest

from xtreme_system.logging.core import configure_logging


def test_configure_logging_preserva_handler_do_pytest(
    caplog: pytest.LogCaptureFixture,
) -> None:
    configure_logging()

    assert caplog.handler in logging.getLogger().handlers
