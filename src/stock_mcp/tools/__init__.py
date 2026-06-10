"""MCP Tools 注册中心"""
from fastmcp import FastMCP
from . import admin, quote, kline


def register_all_tools(mcp: FastMCP, quote_service=None, kline_service=None) -> None:
    """注册所有 MCP tools"""
    admin.register(mcp)
    if quote_service is not None:
        quote.register(mcp, quote_service)
    if kline_service is not None:
        kline.register(mcp, kline_service)
    # 后续阶段加: fundamental, news, query
