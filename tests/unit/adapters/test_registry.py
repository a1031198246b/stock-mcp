from datetime import datetime

import pytest

from stock_mcp.adapters.base import BaseAdapter
from stock_mcp.adapters.registry import AdapterRegistry
from stock_mcp.domain.errors import DataSourceError
from stock_mcp.domain.models import Quote


class FakeAdapter(BaseAdapter):
    def __init__(self, name, priority=1, healthy=True, quote_result=None):
        self.name = name
        self.priority = priority
        self.enabled = True
        self._healthy = healthy
        self._quote_result = quote_result or []
        self.call_count = 0

    async def health_check(self):
        return self._healthy

    async def get_realtime_quote(self, codes):
        self.call_count += 1
        return self._quote_result

    async def get_kline(self, code, period, count):
        return []

    async def get_fundamental(self, code):
        return None

    async def get_news(self, code, limit):
        return []


@pytest.mark.asyncio
async def test_registry_sorts_by_priority():
    a = FakeAdapter("a", priority=2)
    b = FakeAdapter("b", priority=1)
    reg = AdapterRegistry([a, b])
    assert reg.adapters_in_order()[0].name == "b"


@pytest.mark.asyncio
async def test_fallback_to_second_when_first_fails():
    q2 = [
        Quote(
            code="1",
            name="x",
            price=2,
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
            source="a2",
        )
    ]

    class FailingAdapter(FakeAdapter):
        async def get_realtime_quote(self, codes):
            self.call_count += 1
            raise DataSourceError("boom", source=self.name)

    a1 = FailingAdapter("a1", priority=1)
    a2 = FakeAdapter("a2", priority=2, quote_result=q2)
    reg = AdapterRegistry([a1, a2])
    reg.mark_unhealthy("a1")  # 直接标记

    result = await reg.fan_out("get_realtime_quote", codes=["1"])
    assert result[0].price == 2
    assert a2.call_count == 1


@pytest.mark.asyncio
async def test_all_fail_raises():
    class FailAll(FakeAdapter):
        async def get_realtime_quote(self, codes):
            raise DataSourceError("nope", source=self.name)

    reg = AdapterRegistry([FailAll("a1"), FailAll("a2")])
    with pytest.raises(DataSourceError):
        await reg.fan_out("get_realtime_quote", codes=["1"])


@pytest.mark.asyncio
async def test_disabled_adapter_skipped():
    q = [
        Quote(
            code="1",
            name="x",
            price=1,
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
            source="a1",
        )
    ]
    a = FakeAdapter("a", priority=1, quote_result=q)
    a.enabled = False
    reg = AdapterRegistry([a])
    with pytest.raises(DataSourceError):
        await reg.fan_out("get_realtime_quote", codes=["1"])


# ============== 覆盖率补足测试 (CI 在 TDX_PATH="" 下需 ≥ 90%) ==============


def test_mark_healthy_removes_unhealthy_entry():
    """mark_unhealthy / mark_healthy / is_unhealthy 健康状态切换"""
    a = FakeAdapter("a")
    reg = AdapterRegistry([a])
    reg.mark_unhealthy("a", recovery_seconds=300)
    assert reg.is_unhealthy("a") is True
    reg.mark_healthy("a")
    assert reg.is_unhealthy("a") is False


def test_is_unhealthy_false_when_not_marked():
    """未标记的适配器默认是健康的"""
    a = FakeAdapter("a")
    reg = AdapterRegistry([a])
    assert reg.is_unhealthy("a") is False


def test_is_unhealthy_expires_after_deadline(monkeypatch):
    """is_unhealthy 到达 deadline 后, 应当视为健康并自动清理"""
    a = FakeAdapter("a")
    reg = AdapterRegistry([a])
    # 标记极短 deadline, 然后把系统时间"拨快"超过它
    reg.mark_unhealthy("a", recovery_seconds=1)
    # 通过 monkeypatch 控制 time.time 返回值
    import time as _time

    base = _time.time()
    monkeypatch.setattr(_time, "time", lambda: base + 10)
    assert reg.is_unhealthy("a") is False
    # 自愈后, _unhealthy 已被清理
    assert "a" not in reg._unhealthy


@pytest.mark.asyncio
async def test_fan_out_skips_unhealthy_adapter_in_loop():
    """fan_out 内部 is_unhealthy 为真 → 跳过该适配器 (不调用其方法)"""
    q = [
        Quote(
            code="1",
            name="x",
            price=2,
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
            source="a2",
        )
    ]
    a1 = FakeAdapter("a1", priority=1, quote_result=q)
    a2 = FakeAdapter("a2", priority=2, quote_result=q)
    reg = AdapterRegistry([a1, a2])
    # 把 a1 标记为不健康, 让 fan_out 内部"先按 priority 排好, 再 is_unhealthy 过滤"
    reg.mark_unhealthy("a1")
    await reg.fan_out("get_realtime_quote", codes=["1"])
    # a1 被跳过, 不会 call; a2 会被 call
    assert a1.call_count == 0
    assert a2.call_count == 1


@pytest.mark.asyncio
async def test_fan_out_treats_empty_list_as_failure_then_falls_back():
    """返回空列表视为 '真无数据', 应继续 fallback 到下一个适配器"""
    q2 = [
        Quote(
            code="1",
            name="x",
            price=3,
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
            source="a2",
        )
    ]
    a1 = FakeAdapter("a1", priority=1, quote_result=[])  # 空结果
    a2 = FakeAdapter("a2", priority=2, quote_result=q2)  # 有数据
    reg = AdapterRegistry([a1, a2])
    result = await reg.fan_out("get_realtime_quote", codes=["1"])
    assert result[0].price == 3
    assert a2.call_count == 1


@pytest.mark.asyncio
async def test_fan_out_treats_none_result_as_failure_then_falls_back():
    """返回 None 视为 '真无数据', 应继续 fallback 到下一个适配器"""
    q2 = [
        Quote(
            code="1",
            name="x",
            price=4,
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
            source="a2",
        )
    ]

    class NoneAdapter(FakeAdapter):
        async def get_realtime_quote(self, codes):
            self.call_count += 1
            return None

    a1 = NoneAdapter("a1", priority=1)
    a2 = FakeAdapter("a2", priority=2, quote_result=q2)
    reg = AdapterRegistry([a1, a2])
    result = await reg.fan_out("get_realtime_quote", codes=["1"])
    assert result[0].price == 4
    assert a2.call_count == 1


@pytest.mark.asyncio
async def test_fan_out_raises_when_all_return_empty_or_none():
    """所有适配器都返回空/None (不是抛错) → 抛 DataSourceError"""
    a1 = FakeAdapter("a1", priority=1, quote_result=[])

    class NoneAdapter(FakeAdapter):
        async def get_realtime_quote(self, codes):
            return None

    a2 = NoneAdapter("a2", priority=2)
    reg = AdapterRegistry([a1, a2])
    with pytest.raises(DataSourceError):
        await reg.fan_out("get_realtime_quote", codes=["1"])


@pytest.mark.asyncio
async def test_fan_out_raises_when_no_adapters_in_order():
    """所有适配器都 disabled / unhealthy → 抛 DataSourceError('无可用适配器')"""
    a = FakeAdapter("a", priority=1)
    a.enabled = False
    reg = AdapterRegistry([a])
    with pytest.raises(DataSourceError) as ei:
        await reg.fan_out("get_realtime_quote", codes=["1"])
    assert "无可用适配器" in str(ei.value)
