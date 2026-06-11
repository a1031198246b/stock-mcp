import pytest

from stock_mcp.adapters.iwencai import IwencaiAdapter
from stock_mcp.domain.models import StockQueryResult
from stock_mcp.services.query_service import QueryService
from stock_mcp.tools.query import register


class FakeIwencai(IwencaiAdapter):
    def __init__(self, results):
        super().__init__()
        self.enabled = True
        self._results = results

    async def query_stocks(self, condition):
        return self._results


@pytest.mark.asyncio
async def test_query_tool_returns_markdown():
    results = [
        StockQueryResult(code="600519", name="贵州茅台", matched_fields={"ROE": 0.30, "PE": 25.0}),
        StockQueryResult(code="000001", name="平安银行", matched_fields={"ROE": 0.12, "PE": 8.0}),
    ]
    adapter = FakeIwencai(results)
    svc = QueryService(adapter)

    from fastmcp import FastMCP

    mcp = FastMCP("test")
    register(mcp, svc)

    result = await mcp.call_tool("query_stocks", {"condition": "ROE > 0.1"})
    text = result.content[0].text
    assert "600519" in text
    assert "贵州茅台" in text
    assert "ROE" in text


class _AuthErrorAdapter(IwencaiAdapter):
    """Raise AuthError on query_stocks."""

    def __init__(self):
        super().__init__()
        self.enabled = True

    async def query_stocks(self, condition):
        from stock_mcp.domain.errors import AuthError

        raise AuthError("cookie expired", source="iwencai")


class _SourceErrorAdapter(IwencaiAdapter):
    """Raise DataSourceError on query_stocks."""

    def __init__(self):
        super().__init__()
        self.enabled = True

    async def query_stocks(self, condition):
        from stock_mcp.domain.errors import DataSourceError

        raise DataSourceError("parse fail", source="iwencai")


class _EmptyAdapter(IwencaiAdapter):
    """Return empty results list."""

    def __init__(self):
        super().__init__()
        self.enabled = True

    async def query_stocks(self, condition):
        return []


@pytest.mark.asyncio
async def test_query_tool_handles_auth_error():
    """AuthError from adapter → ❌ iwencai auth message returned."""
    from fastmcp import FastMCP

    adapter = _AuthErrorAdapter()
    svc = QueryService(adapter)

    mcp = FastMCP("test")
    register(mcp, svc)

    result = await mcp.call_tool("query_stocks", {"condition": "ROE > 0.1"})
    text = result.content[0].text
    assert "❌" in text
    assert "iwencai 认证失败" in text
    assert "IWENCAI_COOKIE" in text


@pytest.mark.asyncio
async def test_query_tool_handles_data_source_error():
    """DataSourceError from adapter → ❌ query failed message returned."""
    from fastmcp import FastMCP

    adapter = _SourceErrorAdapter()
    svc = QueryService(adapter)

    mcp = FastMCP("test")
    register(mcp, svc)

    result = await mcp.call_tool("query_stocks", {"condition": "ROE > 0.1"})
    text = result.content[0].text
    assert "❌" in text
    assert "查询失败" in text


@pytest.mark.asyncio
async def test_query_tool_returns_error_when_empty():
    """Empty results → ❌ not-found message returned."""
    from fastmcp import FastMCP

    adapter = _EmptyAdapter()
    svc = QueryService(adapter)

    mcp = FastMCP("test")
    register(mcp, svc)

    result = await mcp.call_tool("query_stocks", {"condition": "ROE > 0.1"})
    text = result.content[0].text
    assert "❌" in text
    assert "未找到符合条件的股票" in text
