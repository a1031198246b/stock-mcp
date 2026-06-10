"""MCP Server 入口 - stdio 模式"""
import sys
from fastmcp import FastMCP
from .config import get_settings
from .logging_setup import setup_logging
from .tools import register_all_tools
from .adapters.tqcenter import TqcenterAdapter
from .adapters.registry import AdapterRegistry
from .services.quote_service import QuoteService, InMemoryQuoteCache


def create_server() -> FastMCP:
    """创建并配置 MCP server"""
    setup_logging()
    mcp = FastMCP("stock-mcp")

    # 初始化 tqcenter 适配器
    tq_adapter = TqcenterAdapter()
    tq_adapter.initialize()

    registry = AdapterRegistry([tq_adapter])
    quote_service = QuoteService(registry, InMemoryQuoteCache())

    register_all_tools(mcp, quote_service=quote_service)
    return mcp


def main() -> None:
    mcp = create_server()
    mcp.run(transport="stdio")


if __name__ == "__main__":
    main()
