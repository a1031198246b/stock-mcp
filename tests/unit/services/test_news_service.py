import pytest
import tempfile
from pathlib import Path
from datetime import datetime
from stock_mcp.services.news_service import NewsService
from stock_mcp.adapters.base import BaseAdapter
from stock_mcp.adapters.registry import AdapterRegistry
from stock_mcp.domain.models import NewsItem
from stock_mcp.cache.sqlite_cache import SQLiteCache
from stock_mcp.cache.ttl import TTLCalculator


class FakeNewsAdapter(BaseAdapter):
    def __init__(self, news):
        self._news = news
        self.name = "fake"
        self.priority = 1
        self.enabled = True
        self.call_count = 0
    async def get_realtime_quote(self, codes): return []
    async def get_kline(self, code, period, count): return []
    async def get_fundamental(self, code): return None
    async def get_news(self, code, limit):
        self.call_count += 1
        return [n for n in self._news if n.code == code][:limit]


@pytest.fixture
async def sqlite_cache():
    with tempfile.TemporaryDirectory() as tmpdir:
        yield SQLiteCache(Path(tmpdir) / "test.db")


@pytest.fixture
def ttl_calc():
    return TTLCalculator()


@pytest.mark.asyncio
async def test_get_news_caches(sqlite_cache, ttl_calc):
    news = [
        NewsItem(code="600519", title="茅台公告", url="http://x", publish_time=datetime(2026, 6, 10), source="eastmoney"),
    ]
    adapter = FakeNewsAdapter(news)
    svc = NewsService(AdapterRegistry([adapter]), sqlite_cache, ttl_calc)

    r1 = await svc.get_news("600519", limit=10)
    r2 = await svc.get_news("600519", limit=10)
    assert len(r1) == 1
    assert len(r2) == 1
    assert adapter.call_count == 1
