import structlog

from stock_mcp.logging_setup import get_logger, setup_logging


def test_setup_logging_does_not_crash(monkeypatch):
    monkeypatch.setenv("LOG_LEVEL", "WARNING")
    setup_logging()
    logger = get_logger("test")
    assert isinstance(logger, structlog.stdlib.BoundLogger)
    # 不应抛异常
    logger.warning("test_event", key="value")
