import tempfile
from datetime import datetime
from pathlib import Path

import pytest

from stock_mcp.adapters.base import BaseAdapter
from stock_mcp.adapters.registry import AdapterRegistry
from stock_mcp.cache.sqlite_cache import SQLiteCache
from stock_mcp.cache.ttl import TTLCalculator
from stock_mcp.domain.models import Quote
from stock_mcp.services.quote_service import QuoteService
from stock_mcp.tools.quote import register


class FakeAdapter(BaseAdapter):
    def __init__(self, q):
        self._q = q
        self.name = "fake"
        self.priority = 1
        self.enabled = True

    async def get_realtime_quote(self, codes):
        return [self._q] if self._q.code in codes else []

    async def get_kline(self, code, period, count):
        return []

    async def get_fundamental(self, code):
        return None

    async def get_news(self, code, limit):
        return []


@pytest.mark.asyncio
async def test_quote_tool_returns_list():
    from fastmcp import FastMCP

    q = Quote(
        code="600519",
        name="贵州茅台",
        price=1500.0,
        change_pct=2.5,
        amount=1e9,
        volume=10000,
        open=1480,
        high=1510,
        low=1475,
        last_close=1463.5,
        bid_5=[100] * 5,
        ask_5=[150] * 5,
        timestamp=datetime(2026, 6, 10),
        source="tqcenter",
    )
    adapter = FakeAdapter(q)
    registry = AdapterRegistry([adapter])
    with tempfile.TemporaryDirectory() as tmpdir:
        cache = SQLiteCache(Path(tmpdir) / "test.db")
        ttl_calc = TTLCalculator()
        svc = QuoteService(registry, cache, ttl_calc)

        mcp = FastMCP("test")
        register(mcp, svc)

        # 通过 tool manager 调用
        tools = await mcp.list_tools()
        assert any(t.name == "get_realtime_quote" for t in tools)

        # 直接调用 tool
        result = await mcp.call_tool("get_realtime_quote", {"codes": ["600519"]})
        # FastMCP 3.4.2 返回 ToolResult 对象, 文本在 result.content[0].text
        text = result.content[0].text
        assert "600519" in text
        assert "贵州茅台" in text
        assert "1500" in text


class _ErrorAdapter(BaseAdapter):
    """Raise DataSourceError on get_realtime_quote."""

    def __init__(self):
        self.name = "fake-err"
        self.priority = 1
        self.enabled = True

    async def get_realtime_quote(self, codes):
        from stock_mcp.domain.errors import DataSourceError

        raise DataSourceError("timeout", source="tqcenter")

    async def get_kline(self, code, period, count):
        return []

    async def get_fundamental(self, code):
        return None

    async def get_news(self, code, limit):
        return []


@pytest.mark.asyncio
async def test_quote_tool_handles_data_source_error():
    """DataSourceError from adapter → ❌ error message returned."""
    from fastmcp import FastMCP

    adapter = _ErrorAdapter()
    registry = AdapterRegistry([adapter])
    with tempfile.TemporaryDirectory() as tmpdir:
        cache = SQLiteCache(Path(tmpdir) / "test.db")
        ttl_calc = TTLCalculator()
        svc = QuoteService(registry, cache, ttl_calc)

        mcp = FastMCP("test")
        register(mcp, svc)

        result = await mcp.call_tool("get_realtime_quote", {"codes": ["600519"]})
        text = result.content[0].text
        assert "❌" in text
        assert "数据获取失败" in text
