"""MCP Server 入口 - stdio 模式"""
import sys
from fastmcp import FastMCP
from .config import get_settings
from .logging_setup import setup_logging
from .tools import register_all_tools


def create_server() -> FastMCP:
    """创建并配置 MCP server"""
    setup_logging()
    mcp = FastMCP("stock-mcp")
    register_all_tools(mcp)
    return mcp


def main() -> None:
    """stdio 启动入口"""
    mcp = create_server()
    # FastMCP stdio 模式
    mcp.run(transport="stdio")


if __name__ == "__main__":
    main()
