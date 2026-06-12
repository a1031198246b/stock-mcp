"""验证 service 层按 priority 路由 adapter.

priority 数字小优先, 验证:
- 港美股实时: eastmoney(2) 优先于 sina(5) (字段更稳)
- A 股实时: sina(5) 优先于 tencent(6) (32 字段含五档)
"""

import tempfile
from datetime import datetime
from pathlib import Path

import pytest

from stock_mcp.adapters.base import BaseAdapter
from stock_mcp.adapters.eastmoney import EastmoneyAdapter
from stock_mcp.adapters.registry import AdapterRegistry
from stock_mcp.adapters.sina import SinaAdapter
from stock_mcp.adapters.tencent import TencentAdapter
from stock_mcp.cache.sqlite_cache import SQLiteCache
from stock_mcp.cache.ttl import TTLCalculator
from stock_mcp.domain.models import Quote
from stock_mcp.services.quote_service import QuoteService


class FakeEastmoneyAdapter(BaseAdapter):
    """mock eastmoney 港美股字段稳的版本"""

    def __init__(self):
        self.name = "fake_eastmoney"
        self.priority = 2
        self.enabled = True
        self.supported_markets = ["a_stock", "hk", "us"]
        self.call_count = 0

    async def get_realtime_quote(self, codes, market="a_stock"):
        self.call_count += 1
        if market == "hk":
            return [
                Quote(
                    code=c,
                    name=f"hk-{c}",
                    price=100.0,
                    change_pct=1.0,
                    amount=1e6,
                    volume=100,
                    open=99.0,
                    high=101.0,
                    low=98.0,
                    last_close=99.0,
                    bid_5=[0] * 5,
                    ask_5=[0] * 5,
                    timestamp=datetime.now(),
                    source="fake_eastmoney",
                    market=market,
                )
                for c in codes
            ]
        return []  # A 股不服务

    async def get_kline(self, code, period, count, market="a_stock"):
        return []

    async def get_fundamental(self, code, market="a_stock"):
        return None

    async def get_news(self, code, limit, market="a_stock"):
        return []


class FakeSinaAdapter(BaseAdapter):
    """mock sina A 股 32 字段含五档"""

    def __init__(self):
        self.name = "fake_sina"
        self.priority = 5
        self.enabled = True
        self.supported_markets = ["a_stock", "hk", "us"]
        self.call_count = 0

    async def get_realtime_quote(self, codes, market="a_stock"):
        self.call_count += 1
        return [
            Quote(
                code=c,
                name=f"sina-{c}",
                price=200.0,
                change_pct=2.0,
                amount=2e6,
                volume=200,
                open=199.0,
                high=201.0,
                low=198.0,
                last_close=199.0,
                bid_5=[10] * 5,  # sina 有五档
                ask_5=[10] * 5,
                timestamp=datetime.now(),
                source="fake_sina",
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


@pytest.fixture
async def cache():
    with tempfile.TemporaryDirectory() as tmp:
        yield SQLiteCache(Path(tmp) / "test.db")


@pytest.fixture
def ttl():
    return TTLCalculator()


@pytest.mark.asyncio
async def test_hk_realtime_routes_to_eastmoney_first(cache, ttl):
    """港美股实时: eastmoney(2) 优先于 sina(5), 数据应来自 eastmoney"""
    em = FakeEastmoneyAdapter()
    sina = FakeSinaAdapter()
    reg = AdapterRegistry([sina, em])  # 注册顺序故意 sina 在前, 验证 priority 排序生效
    svc = QuoteService(reg, cache, ttl)

    quotes = await svc.get_realtime_quote(["00700"], market="hk")
    assert len(quotes) == 1
    q = quotes[0]
    assert q.source == "fake_eastmoney", (
        f"应来自 eastmoney (priority=2), 实际: {q.source} "
        f"(sina 字段虽然有五档但盘前盘后错位, 不应优先)"
    )
    assert em.call_count == 1
    assert sina.call_count == 0  # sina 不该被调用


@pytest.mark.asyncio
async def test_a_stock_realtime_routes_to_sina_first(cache, ttl):
    """A 股实时: sina(5) 有五档, 优先于 eastmoney(2, 但 A 股返回 [])"""
    em = FakeEastmoneyAdapter()
    sina = FakeSinaAdapter()
    reg = AdapterRegistry([em, sina])  # 故意 eastmoney 在前
    svc = QuoteService(reg, cache, ttl)

    quotes = await svc.get_realtime_quote(["600519"], market="a_stock")
    assert len(quotes) == 1
    q = quotes[0]
    # A 股 优先级: tqcenter(1) > eastmoney(2) > ... > sina(5)
    # eastmoney a_stock 返回 [] → 落到 sina
    assert q.source == "fake_sina", f"A 股应来自 sina, 实际: {q.source}"
    assert sina.call_count == 1
    assert em.call_count == 1  # eastmoney 试过, 但返回 []


@pytest.mark.asyncio
async def test_real_adapter_priorities_match_design(cache, ttl):
    """验证真实 adapter 的 priority 是按设计:
    - eastmoney(2) < sina(5) < tencent(6) < yfinance(7)
    - tqcenter(1) < baostock(3) < akshare(4)
    """
    # 真实 adapter (不实际调用, 只验证 priority 字段)
    assert EastmoneyAdapter.priority < SinaAdapter.priority, "eastmoney 港美股字段稳, 应优先 sina"
    assert SinaAdapter.priority < TencentAdapter.priority, "sina A 股五档优于 tencent"
    assert TencentAdapter.priority < 7, "tencent 应该在 yfinance 之前"
    # baostock 应该在 eastmoney 之后 (A 股 K线, 不影响港美股)
    from stock_mcp.adapters.baostock_source import BaostockAdapter

    assert BaostockAdapter.priority > EastmoneyAdapter.priority


@pytest.mark.asyncio
async def test_hk_falls_back_to_sina_when_eastmoney_fails(cache, ttl):
    """港美股 eastmoney 失败 → fallback 到 sina (有五档但字段盘中 OK)"""

    class FailingEastmoney(FakeEastmoneyAdapter):
        async def get_realtime_quote(self, codes, market="a_stock"):
            from stock_mcp.domain.errors import DataSourceError

            raise DataSourceError("eastmoney 挂了", source=self.name)

    em = FailingEastmoney()
    sina = FakeSinaAdapter()
    reg = AdapterRegistry([em, sina])
    svc = QuoteService(reg, cache, ttl)

    quotes = await svc.get_realtime_quote(["00700"], market="hk")
    assert len(quotes) == 1
    assert quotes[0].source == "fake_sina", "eastmoney 失败应 fallback sina"
