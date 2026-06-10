import pytest
from datetime import datetime
from stock_mcp.services.quote_service import QuoteService
from stock_mcp.adapters.base import BaseAdapter
from stock_mcp.adapters.registry import AdapterRegistry
from stock_mcp.domain.models import Quote
from stock_mcp.domain.errors import DataSourceError


class FakeAdapter(BaseAdapter):
    def __init__(self, name, quotes):
        self.name = name
        self.priority = 1
        self.enabled = True
        self._quotes = quotes
        self.call_count = 0

    async def get_realtime_quote(self, codes):
        self.call_count += 1
        return [q for q in self._quotes if q.code in codes]

    async def get_kline(self, code, period, count): return []
    async def get_fundamental(self, code): return None
    async def get_news(self, code, limit): return []


def make_quote(code, source="x"):
    return Quote(
        code=code, name=code, price=10.0, change_pct=1.0,
        amount=1e6, volume=100, open=10, high=10, low=10, last_close=9.9,
        bid_5=[1]*5, ask_5=[1]*5, timestamp=datetime.now(), source=source,
    )


@pytest.fixture
def in_memory_cache():
    """占位 - P2 阶段替换为 SQLite"""
    from stock_mcp.services.quote_service import InMemoryQuoteCache
    return InMemoryQuoteCache(ttl_seconds=60)


@pytest.mark.asyncio
async def test_get_quote_hits_adapter_first_time(in_memory_cache):
    q = make_quote("600519", "tqcenter")
    adapter = FakeAdapter("tqcenter", [q])
    svc = QuoteService(AdapterRegistry([adapter]), in_memory_cache)
    result = await svc.get_realtime_quote(["600519"])
    assert result[0].code == "600519"
    assert adapter.call_count == 1


@pytest.mark.asyncio
async def test_get_quote_caches_result(in_memory_cache):
    q = make_quote("600519", "tqcenter")
    adapter = FakeAdapter("tqcenter", [q])
    svc = QuoteService(AdapterRegistry([adapter]), in_memory_cache)
    await svc.get_realtime_quote(["600519"])
    await svc.get_realtime_quote(["600519"])  # 第二次应从缓存取
    assert adapter.call_count == 1  # 只调用了一次


@pytest.mark.asyncio
async def test_get_quote_cache_ttl_expiry(in_memory_cache):
    q = make_quote("600519", "tqcenter")
    adapter = FakeAdapter("tqcenter", [q])
    svc = QuoteService(AdapterRegistry([adapter]), in_memory_cache)

    await svc.get_realtime_quote(["600519"])
    in_memory_cache.clear()  # 模拟 TTL 过期
    await svc.get_realtime_quote(["600519"])
    assert adapter.call_count == 2


@pytest.mark.asyncio
async def test_get_quote_fallback_when_primary_fails(in_memory_cache):
    class FailAdapter(FakeAdapter):
        async def get_realtime_quote(self, codes):
            self.call_count += 1
            raise DataSourceError("down", source=self.name)

    a1 = FailAdapter("a1", [])
    a2 = FakeAdapter("a2", [make_quote("600519", "a2")])
    reg = AdapterRegistry([a1, a2])
    svc = QuoteService(reg, in_memory_cache)

    result = await svc.get_realtime_quote(["600519"])
    assert result[0].source == "a2"
    assert a2.call_count == 1
