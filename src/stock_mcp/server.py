"""MCP Server 入口 - stdio 模式"""
import sys
from fastmcp import FastMCP
from .config import get_settings
from .logging_setup import setup_logging
from .tools import register_all_tools
from .adapters.tqcenter import TqcenterAdapter
from .adapters.sina import SinaAdapter
from .adapters.akshare_source import AkshareAdapter
from .adapters.registry import AdapterRegistry
from .cache.sqlite_cache import SQLiteCache
from .cache.ttl import TTLCalculator
from .services.quote_service import QuoteService
from .services.kline_service import KlineService


def create_server() -> FastMCP:
    """创建并配置 MCP server"""
    setup_logging()
    mcp = FastMCP("stock-mcp")
    settings = get_settings()

    # 缓存
    cache = SQLiteCache(settings.cache_db_path)
    ttl_calc = TTLCalculator()

    # 适配器
    tq = TqcenterAdapter(); tq.initialize()
    sina = SinaAdapter()
    akshare = AkshareAdapter()
    registry = AdapterRegistry([tq, sina, akshare])

    # 服务
    quote_service = QuoteService(registry, cache, ttl_calc)
    kline_service = KlineService(registry, cache, ttl_calc)

    register_all_tools(
        mcp, quote_service=quote_service, kline_service=kline_service
    )
    return mcp


def main() -> None:
    mcp = create_server()
    mcp.run(transport="stdio")


if __name__ == "__main__":
    main()
