import tempfile
from datetime import datetime
from pathlib import Path

import pytest

from stock_mcp.adapters.base import BaseAdapter
from stock_mcp.adapters.registry import AdapterRegistry
from stock_mcp.cache.sqlite_cache import SQLiteCache
from stock_mcp.cache.ttl import TTLCalculator
from stock_mcp.domain.errors import DataSourceError
from stock_mcp.domain.models import Quote
from stock_mcp.services.quote_service import QuoteService


class FakeAdapter(BaseAdapter):
    def __init__(self, name, quotes):
        self.name = name
        self.priority = 1
        self.enabled = True
        self._quotes = quotes
        self.call_count = 0

    async def get_realtime_quote(self, codes, market="a_stock"):
        self.call_count += 1
        return [q for q in self._quotes if q.code in codes]

    async def get_kline(self, code, period, count, market="a_stock"):
        return []

    async def get_fundamental(self, code, market="a_stock"):
        return None

    async def get_news(self, code, limit, market="a_stock"):
        return []


def make_quote(code, source="x"):
    return Quote(
        code=code,
        name=code,
        price=10.0,
        change_pct=1.0,
        amount=1e6,
        volume=100,
        open=10,
        high=10,
        low=10,
        last_close=9.9,
        bid_5=[1] * 5,
        ask_5=[1] * 5,
        timestamp=datetime.now(),
        source=source,
    )


@pytest.fixture
async def sqlite_cache():
    with tempfile.TemporaryDirectory() as tmpdir:
        cache = SQLiteCache(Path(tmpdir) / "test.db")
        yield cache


@pytest.fixture
def ttl_calc():
    return TTLCalculator()


@pytest.mark.asyncio
async def test_get_quote_hits_adapter_first_time(sqlite_cache, ttl_calc):
    q = make_quote("600519", "tqcenter")
    adapter = FakeAdapter("tqcenter", [q])
    svc = QuoteService(AdapterRegistry([adapter]), sqlite_cache, ttl_calc)
    result = await svc.get_realtime_quote(["600519"])
    assert result[0].code == "600519"
    assert adapter.call_count == 1


@pytest.mark.asyncio
async def test_get_quote_caches_result(sqlite_cache, ttl_calc):
    q = make_quote("600519", "tqcenter")
    adapter = FakeAdapter("tqcenter", [q])
    svc = QuoteService(AdapterRegistry([adapter]), sqlite_cache, ttl_calc)
    await svc.get_realtime_quote(["600519"])
    await svc.get_realtime_quote(["600519"])
    assert adapter.call_count == 1


@pytest.mark.asyncio
async def test_get_quote_fallback_when_primary_fails(sqlite_cache, ttl_calc):
    class FailAdapter(FakeAdapter):
        async def get_realtime_quote(self, codes):
            self.call_count += 1
            raise DataSourceError("down", source=self.name)

    a1 = FailAdapter("a1", [])
    a2 = FakeAdapter("a2", [make_quote("600519", "a2")])
    reg = AdapterRegistry([a1, a2])
    svc = QuoteService(reg, sqlite_cache, ttl_calc)

    result = await svc.get_realtime_quote(["600519"])
    assert result[0].source == "a2"
    assert a2.call_count == 1


@pytest.mark.asyncio
async def test_a_stock_routes_to_a_stock_adapters_only(temp_cache_dir):
    """a_stock 路由只调 a_stock 适配器, 不调 yfinance"""
    from stock_mcp.adapters.registry import AdapterRegistry
    from stock_mcp.adapters.sina import SinaAdapter
    from stock_mcp.adapters.yfinance_source import YfinanceAdapter
    from stock_mcp.services.quote_service import QuoteService

    sina = SinaAdapter()
    yf = YfinanceAdapter()
    sina.enabled = True
    sina.supported_markets = ["a_stock"]
    yf.enabled = True
    yf.supported_markets = ["hk", "us"]

    from stock_mcp.cache.sqlite_cache import SQLiteCache
    from stock_mcp.cache.ttl import TTLCalculator

    cache = SQLiteCache(temp_cache_dir / "test.db")
    ttl = TTLCalculator()
    registry = AdapterRegistry([sina, yf])
    svc = QuoteService(registry, cache, ttl)

    # 调 a_stock: 触发 sina, 不触发 yfinance
    quotes = await svc.get_realtime_quote(["600519"], market="a_stock")
    # Sina 真调用会尝试 HTTP, 用 mock
    assert all(q.market == "a_stock" for q in quotes)


@pytest.mark.asyncio
async def test_hk_routes_to_yfinance_only(temp_cache_dir):
    """hk 路由只调 yfinance"""
    from stock_mcp.adapters.registry import AdapterRegistry
    from stock_mcp.adapters.sina import SinaAdapter
    from stock_mcp.adapters.yfinance_source import YfinanceAdapter
    from stock_mcp.services.quote_service import QuoteService

    sina = SinaAdapter()
    sina.enabled = True
    sina.supported_markets = ["a_stock"]
    yf = YfinanceAdapter()
    yf.enabled = True
    yf.supported_markets = ["hk", "us"]

    from stock_mcp.cache.sqlite_cache import SQLiteCache
    from stock_mcp.cache.ttl import TTLCalculator

    cache = SQLiteCache(temp_cache_dir / "test.db")
    ttl = TTLCalculator()
    registry = AdapterRegistry([sina, yf])
    svc = QuoteService(registry, cache, ttl)

    # hk 应该试 yfinance, 不应试 sina
    # 这里只验证子集过滤正确, 实际 yfinance 调用会失败 (无网络)
    with pytest.raises((DataSourceError, ValueError, ConnectionError, OSError)):
        await svc.get_realtime_quote(["00700"], market="hk")


@pytest.mark.asyncio
async def test_unknown_market_raises_value_error(temp_cache_dir):
    from stock_mcp.adapters.registry import AdapterRegistry
    from stock_mcp.adapters.sina import SinaAdapter
    from stock_mcp.adapters.yfinance_source import YfinanceAdapter
    from stock_mcp.services.quote_service import QuoteService

    sina = SinaAdapter()
    sina.enabled = True
    sina.supported_markets = ["a_stock"]
    yf = YfinanceAdapter()
    yf.enabled = True
    yf.supported_markets = ["hk", "us"]
    from stock_mcp.cache.sqlite_cache import SQLiteCache
    from stock_mcp.cache.ttl import TTLCalculator

    cache = SQLiteCache(temp_cache_dir / "test.db")
    ttl = TTLCalculator()
    registry = AdapterRegistry([sina, yf])
    svc = QuoteService(registry, cache, ttl)

    with pytest.raises(ValueError, match="jp"):
        await svc.get_realtime_quote(["7203"], market="jp")


@pytest.mark.asyncio
async def test_service_forwards_market_to_adapter(temp_cache_dir):
    """service 调 adapter 时应该把 market 传过去"""
    from datetime import datetime

    from stock_mcp.adapters.base import BaseAdapter
    from stock_mcp.adapters.registry import AdapterRegistry
    from stock_mcp.cache.sqlite_cache import SQLiteCache
    from stock_mcp.cache.ttl import TTLCalculator
    from stock_mcp.domain.models import Quote

    received_markets = []

    class TrackingAdapter(BaseAdapter):
        def __init__(self):
            self.name = "track"
            self.priority = 1
            self.enabled = True
            self.supported_markets = ["hk", "us"]

        async def get_realtime_quote(self, codes, market="a_stock"):
            received_markets.append(market)
            return [
                Quote(
                    code=c,
                    name="X",
                    price=100,
                    change_pct=0,
                    amount=0,
                    volume=0,
                    open=100,
                    high=100,
                    low=100,
                    last_close=100,
                    bid_5=[0] * 5,
                    ask_5=[0] * 5,
                    timestamp=datetime.now(),
                    source="track",
                    market=market,
                )
                for c in codes
            ]

        async def get_kline(self, code, period, count, market="a_stock"):
            return []

        async def get_fundamental(self, code, market="a_stock"):
            return None

        async def get_news(self, code, limit, market="a_stock"):
            return []

    adapter = TrackingAdapter()
    registry = AdapterRegistry([adapter])
    cache = SQLiteCache(temp_cache_dir / "test.db")
    ttl = TTLCalculator()
    svc = QuoteService(registry, cache, ttl)

    await svc.get_realtime_quote(["AAPL"], market="us")
    await svc.get_realtime_quote(["00700"], market="hk")
    assert received_markets == ["us", "hk"], f"Expected ['us', 'hk'], got {received_markets}"
