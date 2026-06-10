import asyncio
import pytest
from stock_mcp.ratelimit.token_bucket import TokenBucket


@pytest.mark.asyncio
async def test_acquire_within_capacity():
    tb = TokenBucket(capacity=5, refill_rate=1)  # 5 个, 1/秒补充
    for _ in range(5):
        assert await tb.acquire() is True
    # 第 6 个应失败
    assert await tb.acquire() is False


@pytest.mark.asyncio
async def test_refill_over_time(freezer):
    tb = TokenBucket(capacity=2, refill_rate=2)  # 2/秒
    await tb.acquire()
    await tb.acquire()
    assert await tb.acquire() is False
    # 推进 1 秒, 应补 2 个
    freezer.tick(1.0)
    assert await tb.acquire() is True
    assert await tb.acquire() is True
    assert await tb.acquire() is False


@pytest.mark.asyncio
async def test_wait_for_token():
    tb = TokenBucket(capacity=1, refill_rate=10)  # 10/秒 = 0.1 秒一个
    await tb.acquire()
    # 等待应能成功（最多等 0.2 秒）
    result = await tb.acquire(timeout=0.5)
    assert result is True
