from datetime import datetime

import pytest
from fastmcp import FastMCP

from stock_mcp.domain.errors import DataSourceError
from stock_mcp.domain.models import FinancialStatement
from stock_mcp.tools.financial_statement import register


class _FakeBaostock:
    """Minimal baostock adapter stub for tool tests."""

    def __init__(self, stmt=None, raise_exc=None, raise_value=None, enabled=True):
        self._stmt = stmt
        self._raise_exc = raise_exc
        self._raise_value = raise_value
        self.enabled = enabled
        self.name = "baostock"
        self.priority = 2
        self.supported_markets = ["a_stock"]

    async def get_financial_statement(self, code, statement_type, market="a_stock"):
        if self._raise_value is not None:
            raise ValueError(self._raise_value)
        if self._raise_exc is not None:
            raise DataSourceError(self._raise_exc, source="baostock")
        assert code == "600519"
        assert market == "a_stock"
        return self._stmt


def _make_stmt(data=None):
    if data is None:
        data = {
            "code": ["600519", "600519"],
            "pubDate": ["2025-04-30", "2025-04-30"],
            "statDate": ["2025-03-31", "2024-12-31"],
            "revenue": ["500.0亿", "1700.0亿"],
        }
    return FinancialStatement(
        code="600519",
        name="贵州茅台",
        market="a_stock",
        period="2025Q1",
        statement_type="income",
        data=data,
        source="baostock",
        fetched_at=datetime(2026, 6, 12),
    )


@pytest.mark.asyncio
async def test_financial_statement_tool_renders_markdown():
    """正常数据 → 工具返回 markdown 表格."""
    adapter = _FakeBaostock(stmt=_make_stmt())
    mcp = FastMCP("test")
    register(mcp, adapter)

    result = await mcp.call_tool(
        "get_financial_statement",
        {"code": "600519", "statement_type": "income", "market": "a_stock"},
    )
    text = result.content[0].text
    assert "600519" in text
    assert "贵州茅台" in text
    assert "利润表" in text
    assert "2025Q1" in text
    assert "|" in text  # markdown table


@pytest.mark.asyncio
async def test_financial_statement_tool_handles_disabled_adapter():
    """adapter 不可用 (None 或 enabled=False) → 友好错误."""
    mcp = FastMCP("test")
    register(mcp, None)

    result = await mcp.call_tool(
        "get_financial_statement", {"code": "600519"}
    )
    text = result.content[0].text
    assert "❌" in text
    assert "baostock" in text

    mcp2 = FastMCP("test")
    register(mcp2, _FakeBaostock(enabled=False))
    result2 = await mcp2.call_tool(
        "get_financial_statement", {"code": "600519"}
    )
    text2 = result2.content[0].text
    assert "❌" in text2


@pytest.mark.asyncio
async def test_financial_statement_tool_handles_value_error():
    """ValueError → 参数错错误."""
    adapter = _FakeBaostock(raise_value="invalid statement_type")
    mcp = FastMCP("test")
    register(mcp, adapter)

    result = await mcp.call_tool(
        "get_financial_statement", {"code": "600519", "statement_type": "bogus"}
    )
    text = result.content[0].text
    assert "❌" in text
    assert "参数错" in text


@pytest.mark.asyncio
async def test_financial_statement_tool_handles_data_source_error():
    """DataSourceError → baostock 失败错误."""
    adapter = _FakeBaostock(raise_exc="network timeout")
    mcp = FastMCP("test")
    register(mcp, adapter)

    result = await mcp.call_tool(
        "get_financial_statement", {"code": "600519"}
    )
    text = result.content[0].text
    assert "❌" in text
    assert "baostock 失败" in text


@pytest.mark.asyncio
async def test_financial_statement_tool_handles_empty_data():
    """stmt.data 空 → 友好错误."""
    stmt = _make_stmt(data={})
    adapter = _FakeBaostock(stmt=stmt)
    mcp = FastMCP("test")
    register(mcp, adapter)

    result = await mcp.call_tool(
        "get_financial_statement", {"code": "600519"}
    )
    text = result.content[0].text
    assert "❌" in text
    assert "无" in text


@pytest.mark.asyncio
async def test_financial_statement_tool_handles_unknown_statement_type_label():
    """_statement_label fallback → 返回原类型名."""
    stmt = _make_stmt()
    stmt.statement_type = "unknown"
    adapter = _FakeBaostock(stmt=stmt)
    mcp = FastMCP("test")
    register(mcp, adapter)

    result = await mcp.call_tool(
        "get_financial_statement",
        {"code": "600519", "statement_type": "unknown"},
    )
    text = result.content[0].text
    assert "财务unknown" in text
