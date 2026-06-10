"""MCP Tools 注册中心"""
from fastmcp import FastMCP
from . import admin, quote, kline, fundamental, news, query


def register_all_tools(mcp: FastMCP, quote_service=None, kline_service=None,
                       fundamental_service=None, news_service=None,
                       query_service=None) -> None:
    """注册所有 MCP tools"""
    admin.register(mcp)
    if quote_service is not None:
        quote.register(mcp, quote_service)
    if kline_service is not None:
        kline.register(mcp, kline_service)
    if fundamental_service is not None:
        fundamental.register(mcp, fundamental_service)
    if news_service is not None:
        news.register(mcp, news_service)
    if query_service is not None:
        query.register(mcp, query_service)
