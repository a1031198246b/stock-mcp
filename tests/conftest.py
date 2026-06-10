"""全局 pytest fixtures"""
import asyncio
import os
import tempfile
import time
from pathlib import Path

import pytest


@pytest.fixture(scope="session")
def event_loop():
    loop = asyncio.new_event_loop()
    yield loop
    loop.close()


@pytest.fixture(autouse=True)
def _reset_settings_singleton():
    """每个测试前重置 settings 缓存，使 monkeypatch.setenv 立即生效。"""
    from stock_mcp.config import reset_settings
    reset_settings()
    yield
    reset_settings()


@pytest.fixture
def temp_cache_dir():
    """为每个测试提供独立的临时缓存目录"""
    with tempfile.TemporaryDirectory() as tmpdir:
        yield Path(tmpdir)


@pytest.fixture
def mock_env(monkeypatch):
    """注入测试用环境变量"""
    monkeypatch.setenv("TDX_PATH", "C:/fake/tdx")
    monkeypatch.setenv("LOG_LEVEL", "WARNING")
    monkeypatch.setenv("CACHE_DIR", str(tempfile.gettempdir()))
    yield monkeypatch


class _Freezer:
    """简单的 freezer 助手：通过 time.sleep 推进真实时间。

    注意：本实现并未冻结全局时间，而是真实等待。适用于
    time.monotonic() 等不受 freezegun 影响的计时源。"""

    def tick(self, seconds: float) -> None:
        time.sleep(seconds)


@pytest.fixture
def freezer():
    return _Freezer()
