import pytest
from stock_mcp.adapters.base import BaseAdapter
from stock_mcp.adapters.registry import AdapterRegistry
from stock_mcp.domain.models import Quote, Kline, Fundamental, NewsItem
from datetime import datetime
from stock_mcp.domain.errors import DataSourceError


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
    q1 = [Quote(code="1", name="x", price=1, change_pct=0, amount=0,
                volume=0, open=1, high=1, low=1, last_close=1,
                bid_5=[0]*5, ask_5=[0]*5, timestamp=datetime.now(), source="a1")]
    q2 = [Quote(code="1", name="x", price=2, change_pct=0, amount=0,
                volume=0, open=1, high=1, low=1, last_close=1,
                bid_5=[0]*5, ask_5=[0]*5, timestamp=datetime.now(), source="a2")]

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
    q = [Quote(code="1", name="x", price=1, change_pct=0, amount=0,
               volume=0, open=1, high=1, low=1, last_close=1,
               bid_5=[0]*5, ask_5=[0]*5, timestamp=datetime.now(), source="a1")]
    a = FakeAdapter("a", priority=1, quote_result=q)
    a.enabled = False
    reg = AdapterRegistry([a])
    with pytest.raises(DataSourceError):
        await reg.fan_out("get_realtime_quote", codes=["1"])
