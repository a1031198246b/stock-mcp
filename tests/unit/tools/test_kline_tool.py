"""tools/kline.py 单元测试 — 覆盖 K线工具的三条分支"""

from datetime import datetime
from unittest.mock import AsyncMock

import pytest
from fastmcp import FastMCP

from stock_mcp.adapters.base import BaseAdapter
from stock_mcp.adapters.registry import AdapterRegistry
from stock_mcp.cache.sqlite_cache import SQLiteCache
from stock_mcp.cache.ttl import TTLCalculator
from stock_mcp.domain.errors import DataSourceError
from stock_mcp.domain.models import Kline
from stock_mcp.services.kline_service import KlineService
from stock_mcp.tools.kline import register


class FakeKlineAdapter(BaseAdapter):
    """可控制返回值的 K线 fake adapter"""

    def __init__(self, klines=None, error: Exception | None = None):
        self.name = "fake_kline"
        self.priority = 1
        self.enabled = True
        self._klines = klines or []
        self._error = error
        self.call_count = 0

    async def get_realtime_quote(self, codes):
        return []

    async def get_kline(self, code, period, count):
        self.call_count += 1
        if self._error is not None:
            raise self._error
        return [k for k in self._klines if k.code == code and k.period == period]

    async def get_fundamental(self, code):
        return None

    async def get_news(self, code, limit):
        return []


def _make_kline(code: str = "600519", period: str = "1d", close: float = 103.0) -> Kline:
    return Kline(
        code=code,
        period=period,
        datetime=datetime(2026, 6, 10),
        open=100,
        high=105,
        low=99,
        close=close,
        volume=1_000_000,
        amount=1e8,
    )


def _make_service(adapter: BaseAdapter, temp_cache_dir) -> KlineService:
    """在 temp_cache_dir 提供的存活目录里建 cache + service"""
    cache = SQLiteCache(temp_cache_dir / "test.db")
    ttl_calc = TTLCalculator()
    return KlineService(AdapterRegistry([adapter]), cache, ttl_calc)


@pytest.mark.asyncio
async def test_kline_tool_returns_markdown_table(temp_cache_dir):
    """正常分支: 2 条 K线 → Markdown 表格（端到端）"""
    adapter = FakeKlineAdapter([_make_kline(close=103.0), _make_kline(close=107.0)])
    svc = _make_service(adapter, temp_cache_dir)

    mcp = FastMCP("test")
    register(mcp, svc)

    tools = await mcp.list_tools()
    assert any(t.name == "get_kline" for t in tools)

    result = await mcp.call_tool("get_kline", {"code": "600519", "period": "1d", "count": 2})
    text = result.content[0].text
    assert "600519" in text
    assert "1d" in text
    assert "共 2 条" in text
    assert "| 日期 | 开 | 高 | 低 | 收 |" in text
    assert "100" in text  # open
    assert "105" in text  # high
    assert "103" in text  # close of first kline


@pytest.mark.asyncio
async def test_kline_tool_default_period_and_count(temp_cache_dir):
    """默认参数: period=1d, count=30"""
    adapter = FakeKlineAdapter([_make_kline()])
    svc = _make_service(adapter, temp_cache_dir)

    mcp = FastMCP("test")
    register(mcp, svc)

    # 不传 period/count, 验证默认参数生效
    result = await mcp.call_tool("get_kline", {"code": "600519"})
    text = result.content[0].text
    assert "1d" in text
    assert adapter.call_count == 1


@pytest.mark.asyncio
async def test_kline_tool_returns_empty_message():
    """空数据分支: service 返回 [] → 友好提示（mock service）"""
    svc = AsyncMock()
    svc.get_kline.return_value = []

    mcp = FastMCP("test")
    register(mcp, svc)

    result = await mcp.call_tool("get_kline", {"code": "999999", "period": "1d", "count": 30})
    text = result.content[0].text
    assert "999999" in text
    assert "无 K线数据" in text
    svc.get_kline.assert_awaited_once_with("999999", "1d", 30)


@pytest.mark.asyncio
async def test_kline_tool_handles_data_source_error():
    """错误分支: service 抛 DataSourceError → ❌ 提示（mock service）"""
    svc = AsyncMock()
    svc.get_kline.side_effect = DataSourceError("connect timeout", source="tqcenter")

    mcp = FastMCP("test")
    register(mcp, svc)

    result = await mcp.call_tool("get_kline", {"code": "600519", "period": "1d", "count": 30})
    text = result.content[0].text
    assert "❌" in text
    assert "K线获取失败" in text
    assert "connect timeout" in text


@pytest.mark.asyncio
async def test_kline_tool_handles_real_service_with_all_adapters_failing(temp_cache_dir):
    """端到端错误分支: registry 全部失败 → DataSourceError → ❌ 提示"""
    adapter = FakeKlineAdapter(error=DataSourceError("原始错误", source="fake_kline"))
    svc = _make_service(adapter, temp_cache_dir)

    mcp = FastMCP("test")
    register(mcp, svc)

    result = await mcp.call_tool("get_kline", {"code": "600519", "period": "1d", "count": 30})
    text = result.content[0].text
    # registry 会聚合错误, 但 tool 仍捕获到 DataSourceError
    assert "❌" in text
    assert "K线获取失败" in text
