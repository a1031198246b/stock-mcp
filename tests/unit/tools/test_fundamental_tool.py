import tempfile
from pathlib import Path

import pytest

from stock_mcp.adapters.base import BaseAdapter
from stock_mcp.adapters.registry import AdapterRegistry
from stock_mcp.cache.sqlite_cache import SQLiteCache
from stock_mcp.cache.ttl import TTLCalculator
from stock_mcp.domain.models import Fundamental
from stock_mcp.services.fundamental_service import FundamentalService
from stock_mcp.tools.fundamental import register


class FakeAdapter(BaseAdapter):
    def __init__(self, fund):
        self._f = fund
        self.name = "fake"
        self.priority = 1
        self.enabled = True

    async def get_realtime_quote(self, codes):
        return []

    async def get_kline(self, code, period, count):
        return []

    async def get_fundamental(self, code):
        return self._f if code == self._f.code else None

    async def get_news(self, code, limit):
        return []


@pytest.mark.asyncio
async def test_fundamental_tool_returns_markdown():
    from fastmcp import FastMCP

    fund = Fundamental(
        code="600519",
        name="贵州茅台",
        pe=25.5,
        pb=8.2,
        roe=0.30,
        total_shares=12.56,
        market_cap=18840.0,
        industry="白酒",
        source="akshare",
    )
    adapter = FakeAdapter(fund)
    registry = AdapterRegistry([adapter])

    with tempfile.TemporaryDirectory() as tmpdir:
        cache = SQLiteCache(Path(tmpdir) / "test.db")
        ttl_calc = TTLCalculator()
        svc = FundamentalService(registry, cache, ttl_calc)

        mcp = FastMCP("test")
        register(mcp, svc)

        tools = await mcp.list_tools()
        assert any(t.name == "get_fundamental" for t in tools)

        result = await mcp.call_tool("get_fundamental", {"code": "600519"})
        text = result.content[0].text
        assert "600519" in text
        assert "贵州茅台" in text
        assert "25.5" in text


class _ErrorAdapter(BaseAdapter):
    """Raise DataSourceError on get_fundamental."""

    def __init__(self):
        self.name = "fake-err"
        self.priority = 1
        self.enabled = True

    async def get_realtime_quote(self, codes):
        return []

    async def get_kline(self, code, period, count):
        return []

    async def get_fundamental(self, code):
        from stock_mcp.domain.errors import DataSourceError

        raise DataSourceError("parse fail", source="akshare")

    async def get_news(self, code, limit):
        return []


@pytest.mark.asyncio
async def test_fundamental_tool_handles_data_source_error():
    """DataSourceError from adapter → ❌ error message returned."""
    from fastmcp import FastMCP

    adapter = _ErrorAdapter()
    registry = AdapterRegistry([adapter])
    with tempfile.TemporaryDirectory() as tmpdir:
        cache = SQLiteCache(Path(tmpdir) / "test.db")
        ttl_calc = TTLCalculator()
        svc = FundamentalService(registry, cache, ttl_calc)

        mcp = FastMCP("test")
        register(mcp, svc)

        result = await mcp.call_tool("get_fundamental", {"code": "600519"})
        text = result.content[0].text
        assert "❌" in text
        assert "基本面获取失败" in text


# Note: tool 的 `if fund is None:` 分支在当前 service/registry 架构下不可达:
# - FundamentalService.get_fundamental() 把 registry.fan_out 的结果原样返回
# - registry.fan_out 收到 None 会视为"适配器失败"继续 fallback, 全部失败抛 DataSourceError
# - 因此 None 情况实际走的是 except DataSourceError 分支, tool 的 None 分支是死代码
# 跳过对该分支的覆盖测试, 已通过 test_fundamental_tool_handles_data_source_error 覆盖
# 主要错误路径.
