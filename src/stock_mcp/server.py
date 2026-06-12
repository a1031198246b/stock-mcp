"""MCP Server 入口 - stdio 模式"""

from fastmcp import FastMCP

from .adapters.akshare_source import AkshareAdapter
from .adapters.baostock_source import BaostockAdapter
from .adapters.eastmoney import EastmoneyAdapter
from .adapters.iwencai import IwencaiAdapter
from .adapters.registry import AdapterRegistry
from .adapters.sina import SinaAdapter
from .adapters.tencent import TencentAdapter
from .adapters.tqcenter import TqcenterAdapter
from .adapters.yfinance_source import YfinanceAdapter
from .cache.sqlite_cache import SQLiteCache
from .cache.ttl import TTLCalculator
from .config import get_settings
from .logging_setup import setup_logging
from .services.fundamental_service import FundamentalService
from .services.kline_service import KlineService
from .services.news_service import NewsService
from .services.query_service import QueryService
from .services.quote_service import QuoteService
from .tools import register_all_tools


def create_server() -> FastMCP:
    """创建并配置 MCP server"""
    setup_logging()
    mcp = FastMCP("stock-mcp")
    settings = get_settings()

    cache = SQLiteCache(settings.cache_db_path)
    ttl_calc = TTLCalculator()

    tq = TqcenterAdapter()
    tq.initialize()
    sina = SinaAdapter()
    akshare = AkshareAdapter()
    eastmoney = EastmoneyAdapter()
    iwencai = IwencaiAdapter()
    iwencai.initialize()
    bao = BaostockAdapter()
    yf = YfinanceAdapter()
    tencent = TencentAdapter()

    registry = AdapterRegistry([tq, sina, akshare, eastmoney, iwencai, bao, yf, tencent])

    quote_service = QuoteService(registry, cache, ttl_calc)
    kline_service = KlineService(registry, cache, ttl_calc)
    fundamental_service = FundamentalService(registry, cache, ttl_calc)
    news_service = NewsService(registry, cache, ttl_calc)
    query_service = QueryService(iwencai)

    register_all_tools(
        mcp,
        quote_service=quote_service,
        kline_service=kline_service,
        fundamental_service=fundamental_service,
        news_service=news_service,
        query_service=query_service,
        baostock_adapter=bao,
    )
    return mcp


def main() -> None:
    mcp = create_server()
    mcp.run(transport="stdio")


if __name__ == "__main__":
    main()
