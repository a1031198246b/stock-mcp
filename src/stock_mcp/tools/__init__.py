"""MCP Tools 注册中心"""
from fastmcp import FastMCP
from . import admin  # admin 工具最先注册（用于健康检查）


def register_all_tools(mcp: FastMCP) -> None:
    """注册所有 MCP tools"""
    admin.register(mcp)
    # 后续阶段加: quote, kline, fundamental, news, query
