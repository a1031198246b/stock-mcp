import pytest
from stock_mcp.tools.query import register
from stock_mcp.domain.models import StockQueryResult
from stock_mcp.adapters.iwencai import IwencaiAdapter
from stock_mcp.services.query_service import QueryService


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
