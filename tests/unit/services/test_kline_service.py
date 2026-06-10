import pytest
from datetime import datetime
from stock_mcp.services.kline_service import KlineService, InMemoryKlineCache
from stock_mcp.adapters.base import BaseAdapter
from stock_mcp.adapters.registry import AdapterRegistry
from stock_mcp.domain.models import Kline


class FakeKlineAdapter(BaseAdapter):
    def __init__(self, klines):
        self._klines = klines
        self.name = "fake"
        self.priority = 1
        self.enabled = True
        self.call_count = 0
    async def get_realtime_quote(self, codes): return []
    async def get_kline(self, code, period, count):
        self.call_count += 1
        return [k for k in self._klines if k.code == code and k.period == period]
    async def get_fundamental(self, code): return None
    async def get_news(self, code, limit): return []


def make_kline(code="600519", period="1d"):
    return Kline(
        code=code, period=period, datetime=datetime(2026, 6, 10),
        open=100, high=105, low=99, close=103, volume=1000, amount=1e7,
    )


@pytest.mark.asyncio
async def test_get_kline_caches():
    adapter = FakeKlineAdapter([make_kline()])
    cache = InMemoryKlineCache()
    svc = KlineService(AdapterRegistry([adapter]), cache)

    await svc.get_kline("600519", "1d", 1)
    await svc.get_kline("600519", "1d", 1)
    assert adapter.call_count == 1
