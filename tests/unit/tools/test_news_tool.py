from datetime import datetime

import pytest

from stock_mcp.adapters.base import BaseAdapter
from stock_mcp.adapters.registry import AdapterRegistry
from stock_mcp.domain.models import NewsItem
from stock_mcp.services.news_service import NewsService
from stock_mcp.tools.news import register


class FakeAdapter(BaseAdapter):
    def __init__(self, news):
        self._news = news
        self.name = "fake"
        self.priority = 1
        self.enabled = True

    async def get_realtime_quote(self, codes):
        return []

    async def get_kline(self, code, period, count):
        return []

    async def get_fundamental(self, code):
        return None

    async def get_news(self, code, limit):
        return [n for n in self._news if n.code == code][:limit]


@pytest.mark.asyncio
async def test_news_tool_returns_markdown():
    import tempfile
    from pathlib import Path

    from stock_mcp.cache.sqlite_cache import SQLiteCache
    from stock_mcp.cache.ttl import TTLCalculator

    news = [
        NewsItem(
            code="600519",
            title="茅台公告",
            url="http://x.com/1",
            publish_time=datetime(2026, 6, 10, 10, 30),
            source="eastmoney",
        ),
        NewsItem(
            code="600519",
            title="白酒板块走强",
            url="http://x.com/2",
            publish_time=datetime(2026, 6, 10, 9, 15),
            source="证券时报",
        ),
    ]
    adapter = FakeAdapter(news)
    registry = AdapterRegistry([adapter])

    with tempfile.TemporaryDirectory() as tmpdir:
        cache = SQLiteCache(Path(tmpdir) / "test.db")
        ttl_calc = TTLCalculator()
        svc = NewsService(registry, cache, ttl_calc)

        from fastmcp import FastMCP

        mcp = FastMCP("test")
        register(mcp, svc)

        result = await mcp.call_tool("get_news", {"code": "600519", "limit": 10})
        text = result.content[0].text
        assert "茅台公告" in text
        assert "白酒板块走强" in text
        assert "eastmoney" in text or "证券时报" in text
