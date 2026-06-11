import time
from datetime import datetime

import pytest

from stock_mcp.cache.sqlite_cache import SQLiteCache
from stock_mcp.domain.models import Quote


@pytest.mark.asyncio
async def test_set_and_get(temp_cache_dir):
    cache = SQLiteCache(temp_cache_dir / "test.db")
    q = Quote(
        code="600519",
        name="x",
        price=1.0,
        change_pct=0,
        amount=0,
        volume=0,
        open=1,
        high=1,
        low=1,
        last_close=1,
        bid_5=[0] * 5,
        ask_5=[0] * 5,
        timestamp=datetime.now(),
    )
    await cache.set("quote:600519", q.model_dump_json(), ttl=60)
    val = await cache.get("quote:600519")
    assert val is not None
    parsed = Quote.model_validate_json(val)
    assert parsed.code == "600519"


@pytest.mark.asyncio
async def test_ttl_expiry(temp_cache_dir):
    cache = SQLiteCache(temp_cache_dir / "test.db")
    await cache.set("k1", "v1", ttl=1)
    time.sleep(1.2)
    val = await cache.get("k1")
    assert val is None


@pytest.mark.asyncio
async def test_delete_pattern(temp_cache_dir):
    cache = SQLiteCache(temp_cache_dir / "test.db")
    await cache.set("quote:600519", "v1", ttl=60)
    await cache.set("quote:000001", "v2", ttl=60)
    await cache.set("kline:600519", "v3", ttl=60)
    deleted = await cache.delete_pattern("quote:*")
    assert deleted == 2
    assert await cache.get("kline:600519") == "v3"


@pytest.mark.asyncio
async def test_write_failure_does_not_crash(temp_cache_dir, monkeypatch):
    cache = SQLiteCache(temp_cache_dir / "test.db")

    # Mock aiosqlite.connect to raise so the try/except in set()/get() is exercised.
    # aiosqlite.connect is a sync function that returns a coroutine; we make it
    # raise at call-time (synchronously) to match real call shape and avoid
    # "coroutine was never awaited" warnings.
    def fake_connect(*args, **kwargs):
        raise Exception("disk full")

    monkeypatch.setattr("stock_mcp.cache.sqlite_cache.aiosqlite.connect", fake_connect)
    # 不应抛
    await cache.set("k1", "v1", ttl=60)
    # get should also not raise
    val = await cache.get("k1")
    assert val is None


@pytest.mark.asyncio
async def test_delete_pattern_failure_does_not_crash(temp_cache_dir, monkeypatch):
    """delete_pattern 走 aiosqlite.connect 失败路径 → log warning + 返回 0, 不抛."""
    cache = SQLiteCache(temp_cache_dir / "test.db")

    def fake_connect(*args, **kwargs):
        raise Exception("disk full")

    monkeypatch.setattr("stock_mcp.cache.sqlite_cache.aiosqlite.connect", fake_connect)
    # 不应抛
    deleted = await cache.delete_pattern("quote:*")
    assert deleted == 0
