"""tools/__init__.py 单元测试 — register_all_tools 注册逻辑"""

from unittest.mock import MagicMock

import pytest
from fastmcp import FastMCP

from stock_mcp.tools import register_all_tools


@pytest.mark.asyncio
async def test_admin_tool_always_registered():
    """admin 工具（ping）总是注册, 不需要 service"""
    mcp = FastMCP("test")
    register_all_tools(mcp)

    tools = await mcp.list_tools()
    assert any(t.name == "ping" for t in tools)


@pytest.mark.asyncio
async def test_quote_tool_registered_when_service_provided():
    """提供 quote_service → 注册 get_realtime_quote"""
    mcp = FastMCP("test")
    register_all_tools(mcp, quote_service=MagicMock())

    tools = await mcp.list_tools()
    assert any(t.name == "get_realtime_quote" for t in tools)


@pytest.mark.asyncio
async def test_quote_tool_not_registered_when_service_none():
    """quote_service=None → 不注册 get_realtime_quote"""
    mcp = FastMCP("test")
    register_all_tools(mcp, quote_service=None)

    tools = await mcp.list_tools()
    assert not any(t.name == "get_realtime_quote" for t in tools)


@pytest.mark.asyncio
async def test_kline_tool_registered_when_service_provided():
    """提供 kline_service → 注册 get_kline"""
    mcp = FastMCP("test")
    register_all_tools(mcp, kline_service=MagicMock())

    tools = await mcp.list_tools()
    assert any(t.name == "get_kline" for t in tools)


@pytest.mark.asyncio
async def test_fundamental_tool_registered_when_service_provided():
    """提供 fundamental_service → 注册 get_fundamental"""
    mcp = FastMCP("test")
    register_all_tools(mcp, fundamental_service=MagicMock())

    tools = await mcp.list_tools()
    assert any(t.name == "get_fundamental" for t in tools)


@pytest.mark.asyncio
async def test_news_tool_registered_when_service_provided():
    """提供 news_service → 注册 get_news"""
    mcp = FastMCP("test")
    register_all_tools(mcp, news_service=MagicMock())

    tools = await mcp.list_tools()
    assert any(t.name == "get_news" for t in tools)


@pytest.mark.asyncio
async def test_query_tool_registered_when_service_provided():
    """提供 query_service → 注册 query_stocks"""
    mcp = FastMCP("test")
    register_all_tools(mcp, query_service=MagicMock())

    tools = await mcp.list_tools()
    assert any(t.name == "query_stocks" for t in tools)


@pytest.mark.asyncio
async def test_all_services_register_all_tools():
    """所有 service 传入 → 6 个工具全部注册"""
    mcp = FastMCP("test")
    register_all_tools(
        mcp,
        quote_service=MagicMock(),
        kline_service=MagicMock(),
        fundamental_service=MagicMock(),
        news_service=MagicMock(),
        query_service=MagicMock(),
    )

    tools = await mcp.list_tools()
    names = {t.name for t in tools}
    expected = {
        "ping",
        "get_realtime_quote",
        "get_kline",
        "get_fundamental",
        "get_news",
        "query_stocks",
    }
    assert expected.issubset(names)
