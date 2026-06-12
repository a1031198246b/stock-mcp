"""结构化日志初始化"""

import logging
import sys

import structlog

from .config import get_settings


def setup_logging() -> None:
    """初始化 structlog，输出 JSON 到 stderr（stdio MCP 模式下 stdout 是协议通道）"""
    settings = get_settings()
    level = getattr(logging, settings.log_level.upper(), logging.INFO)

    # 标准 logging 桥接到 stderr（stdout 留给 MCP stdio 协议）
    logging.basicConfig(
        format="%(message)s",
        stream=sys.stderr,
        level=level,
    )

    structlog.configure(
        processors=[
            structlog.contextvars.merge_contextvars,
            structlog.processors.add_log_level,
            structlog.processors.TimeStamper(fmt="iso", utc=True),
            structlog.processors.StackInfoRenderer(),
            structlog.processors.format_exc_info,
            structlog.processors.JSONRenderer(),
        ],
        wrapper_class=structlog.stdlib.BoundLogger,
        context_class=dict,
        logger_factory=structlog.PrintLoggerFactory(file=sys.stderr),
        cache_logger_on_first_use=True,
    )


def get_logger(name: str = "stock_mcp") -> structlog.stdlib.BoundLogger:
    from typing import cast

    return cast(structlog.stdlib.BoundLogger, structlog.get_logger(name).bind())
