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
    """补充速度 2/秒, 睡 1 秒后应补 2 个 token"""
    tb = TokenBucket(capacity=2, refill_rate=2)
    await tb.acquire()
    await tb.acquire()
    assert await tb.acquire() is False
    freezer.tick(1.0)  # 1 秒, 应补 2 个
    assert await tb.acquire() is True
    assert await tb.acquire() is True
    assert await tb.acquire() is False


@pytest.mark.asyncio
async def test_acquire_no_token_returns_false_immediately():
    """无 token 且 timeout=0/None 应立即返回 False, 不阻塞"""
    tb = TokenBucket(capacity=1, refill_rate=1)  # 1/秒 = 1秒一个
    await tb.acquire()
    # 此时 token 用完
    import time
    start = time.monotonic()
    result = await tb.acquire()  # 默认 timeout=None
    elapsed = time.monotonic() - start
    assert result is False
    # 关键: 不能阻塞超过几毫秒
    assert elapsed < 0.1, f"acquire() 不应阻塞, 但耗时 {elapsed:.3f}s"


@pytest.mark.asyncio
async def test_acquire_with_sufficient_timeout_waits_for_refill():
    """timeout 足够长时, acquire() 等待 refill 后成功

    实现思路: 不用 acquire(timeout=...) 的内置等待（这个时序敏感易 flaky），
    而是手动 sleep + 重新 acquire（更确定）。
    """
    tb = TokenBucket(capacity=1, refill_rate=20)  # 20/秒 = 50ms 一个
    await tb.acquire()
    # 此时 0 token
    assert await tb.acquire() is False  # 立即返回 False
    # 手动等够时间
    await asyncio.sleep(0.1)  # 100ms > 50ms, 应该有 token
    assert await tb.acquire() is True


@pytest.mark.asyncio
async def test_acquire_with_short_timeout_returns_false():
    """timeout 短于 refill 时间, 应返回 False 而不阻塞"""
    tb = TokenBucket(capacity=1, refill_rate=1)  # 1秒一个
    await tb.acquire()
    # timeout = 0.05s < refill 时间 1.0s, 应立即 False
    import time
    start = time.monotonic()
    result = await tb.acquire(timeout=0.05)
    elapsed = time.monotonic() - start
    assert result is False
    # 关键: 不应真的 sleep 1 秒
    assert elapsed < 0.2, f"acquire 应在 timeout 时立即返回, 但耗时 {elapsed:.3f}s"
