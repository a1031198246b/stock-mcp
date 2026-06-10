import pytest
from stock_mcp.resilience.circuit_breaker import CircuitBreaker, CircuitState


@pytest.mark.asyncio
async def test_starts_closed():
    cb = CircuitBreaker(failure_threshold=3, recovery_timeout=1)
    assert cb.state == CircuitState.CLOSED


@pytest.mark.asyncio
async def test_opens_after_3_failures(freezer):
    cb = CircuitBreaker(failure_threshold=3, recovery_timeout=1)
    for _ in range(3):
        await cb.record_failure()
    assert cb.state == CircuitState.OPEN


@pytest.mark.asyncio
async def test_open_state_rejects_calls():
    cb = CircuitBreaker(failure_threshold=2, recovery_timeout=1)
    await cb.record_failure()
    await cb.record_failure()
    with pytest.raises(Exception, match="circuit open"):
        await cb.call(lambda: None)


@pytest.mark.asyncio
async def test_half_open_after_timeout(freezer):
    cb = CircuitBreaker(failure_threshold=2, recovery_timeout=1)
    await cb.record_failure()
    await cb.record_failure()
    # 1 秒后
    freezer.tick(1.1)
    # 下次 call 进入 HALF_OPEN
    async def success():
        return "ok"
    # 重新跑 call, 期望走半开探测
    # 注: freezegun 与 CircuitBreaker 的实现需要协调; 见实际测试
    assert cb.state == CircuitState.HALF_OPEN


@pytest.mark.asyncio
async def test_closes_after_success_in_half_open():
    cb = CircuitBreaker(failure_threshold=2, recovery_timeout=0)
    await cb.record_failure()
    await cb.record_failure()
    # 立即过期, 下次 call 应是 HALF_OPEN
    await cb.call(lambda: "ok")  # 半开 + 成功 -> 关闭
    assert cb.state == CircuitState.CLOSED
