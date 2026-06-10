import pytest
from stock_mcp.tools.fundamental import register
from stock_mcp.domain.models import Fundamental
from stock_mcp.adapters.base import BaseAdapter
from stock_mcp.adapters.registry import AdapterRegistry
from stock_mcp.services.fundamental_service import FundamentalService


class FakeAdapter(BaseAdapter):
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


@pytest.mark.asyncio
async def test_fundamental_tool_returns_markdown():
    import tempfile
    from pathlib import Path
    from stock_mcp.cache.sqlite_cache import SQLiteCache
    from stock_mcp.cache.ttl import TTLCalculator

    fund = Fundamental(
        code="600519", name="贵州茅台", pe=25.5, pb=8.2, roe=0.30,
        total_shares=12.56, market_cap=18840.0, industry="白酒", source="akshare",
    )
    adapter = FakeAdapter(fund)
    registry = AdapterRegistry([adapter])

    with tempfile.TemporaryDirectory() as tmpdir:
        cache = SQLiteCache(Path(tmpdir) / "test.db")
        ttl_calc = TTLCalculator()
        svc = FundamentalService(registry, cache, ttl_calc)

        from fastmcp import FastMCP
        mcp = FastMCP("test")
        register(mcp, svc)

        tools = await mcp.list_tools()
        assert any(t.name == "get_fundamental" for t in tools)

        result = await mcp.call_tool("get_fundamental", {"code": "600519"})
        text = result.content[0].text
        assert "600519" in text
        assert "贵州茅台" in text
        assert "25.5" in text
