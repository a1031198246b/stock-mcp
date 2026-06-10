"""全局 pytest fixtures"""
import asyncio
import os
import tempfile
from pathlib import Path

import pytest


@pytest.fixture(scope="session")
def event_loop():
    loop = asyncio.new_event_loop()
    yield loop
    loop.close()


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
