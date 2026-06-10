import pytest
import tempfile
from pathlib import Path
from stock_mcp.services.fundamental_service import FundamentalService
from stock_mcp.adapters.base import BaseAdapter
from stock_mcp.adapters.registry import AdapterRegistry
from stock_mcp.domain.models import Fundamental
from stock_mcp.cache.sqlite_cache import SQLiteCache
from stock_mcp.cache.ttl import TTLCalculator


class FakeFundAdapter(BaseAdapter):
    def __init__(self, fund):
        self._f = fund
        self.name = "fake"
        self.priority = 1
        self.enabled = True
    async def get_realtime_quote(self, codes): return []
    async def get_kline(self, code, period, count): return []
    async def get_fundamental(self, code):
        return self._f if code == self._f.code else None
    async def get_news(self, code, limit): return []


@pytest.fixture
async def sqlite_cache():
    with tempfile.TemporaryDirectory() as tmpdir:
        yield SQLiteCache(Path(tmpdir) / "test.db")


@pytest.fixture
def ttl_calc():
    return TTLCalculator()


@pytest.mark.asyncio
async def test_get_fundamental_caches(sqlite_cache, ttl_calc):
    fund = Fundamental(code="600519", name="x", pe=25.0, pb=8.0, source="akshare")
    adapter = FakeFundAdapter(fund)
    svc = FundamentalService(AdapterRegistry([adapter]), sqlite_cache, ttl_calc)

    r1 = await svc.get_fundamental("600519")
    r2 = await svc.get_fundamental("600519")
    assert r1.pe == 25.0
    assert r2.pe == 25.0
