"""tools/admin.py 单元测试 — ping 健康检查工具"""
import pytest
from fastmcp import FastMCP

from stock_mcp.tools.admin import register


@pytest.mark.asyncio
async def test_ping_returns_ok():
    """ping 工具应返回 status=ok / service=stock-mcp"""
    mcp = FastMCP("test")
    register(mcp)

    tools = await mcp.list_tools()
    assert any(t.name == "ping" for t in tools)

    result = await mcp.call_tool("ping", {})
    # FastMCP 3.4.2: dict 返回时 content[0] 是 TextContent with text = JSON
    # 但如果工具声明返回 dict, 实际以结构化数据返回
    # 通过 content 取文本
    text = result.content[0].text
    assert "ok" in text
    assert "stock-mcp" in text


@pytest.mark.asyncio
async def test_ping_does_not_require_arguments():
    """ping 工具应无需参数"""
    mcp = FastMCP("test")
    register(mcp)

    # 空参数调用不应抛错
    result = await mcp.call_tool("ping", {})
    assert result is not None
