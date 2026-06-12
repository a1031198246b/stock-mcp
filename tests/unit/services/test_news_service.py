import tempfile
from datetime import datetime
from pathlib import Path

import pytest

from stock_mcp.adapters.base import BaseAdapter
from stock_mcp.adapters.registry import AdapterRegistry
from stock_mcp.cache.sqlite_cache import SQLiteCache
from stock_mcp.cache.ttl import TTLCalculator
from stock_mcp.domain.models import NewsItem
from stock_mcp.services.news_service import NewsService


class FakeNewsAdapter(BaseAdapter):
    def __init__(self, news):
        self._news = news
        self.name = "fake"
        self.priority = 1
        self.enabled = True
        self.call_count = 0

    async def get_realtime_quote(self, codes, market: str = "a_stock"):
        return []

    async def get_kline(self, code, period, count, market: str = "a_stock"):
        return []

    async def get_fundamental(self, code, market: str = "a_stock"):
        return None

    async def get_news(self, code, limit, market: str = "a_stock"):
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
async def test_get_news_does_not_cache(sqlite_cache, ttl_calc):
    """**2026-06-12**: news 不再 cache, 每次直接调 adapter"""
    news = [
        NewsItem(
            code="600519",
            title="茅台公告",
            url="http://x",
            publish_time=datetime(2026, 6, 10),
            source="eastmoney",
        ),
    ]
    adapter = FakeNewsAdapter(news)
    svc = NewsService(AdapterRegistry([adapter]), sqlite_cache, ttl_calc)

    r1 = await svc.get_news("600519", limit=10)
    r2 = await svc.get_news("600519", limit=10)
    assert len(r1) == 1
    assert len(r2) == 1
    # 不 cache 意味着每次都调 adapter
    assert adapter.call_count == 2
