import pytest

from stock_mcp.adapters.base import BaseAdapter
from stock_mcp.domain.models import Quote


class DummyAdapter(BaseAdapter):
    name = "dummy"
    priority = 1
    enabled = True

    async def get_realtime_quote(self, codes):
        return [
            Quote(
                code=codes[0],
                name="x",
                price=1.0,
                change_pct=0,
                amount=0,
                volume=0,
                open=1,
                high=1,
                low=1,
                last_close=1,
                bid_5=[0] * 5,
                ask_5=[0] * 5,
                timestamp=pytest.importorskip("datetime").datetime.now(),
            )
        ]

    async def get_kline(self, code, period, count):
        return []

    async def get_fundamental(self, code):
        return None

    async def get_news(self, code, limit):
        return []


@pytest.mark.asyncio
async def test_abstract_methods_must_be_implemented():
    """未实现抽象方法的子类不能实例化"""

    class Incomplete(BaseAdapter):
        name = "x"
        priority = 1
        enabled = True
        # 没实现任何方法

    with pytest.raises(TypeError):
        Incomplete()


@pytest.mark.asyncio
async def test_concrete_adapter_works():
    a = DummyAdapter()
    quotes = await a.get_realtime_quote(["600519"])
    assert quotes[0].code == "600519"
    assert quotes[0].source == "dummy"


@pytest.mark.asyncio
async def test_query_stocks_default_raises():
    a = DummyAdapter()
    with pytest.raises(NotImplementedError):
        await a.query_stocks("条件")


@pytest.mark.asyncio
async def test_health_check_default_true():
    a = DummyAdapter()
    assert await a.health_check() is True


class _BaseCallingAdapter(BaseAdapter):
    """调用 super() 触发 BaseAdapter 抽象方法体的 NotImplementedError 抛点."""

    name = "passthrough"
    priority = 1
    enabled = True

    async def get_realtime_quote(self, codes):
        return await BaseAdapter.get_realtime_quote(self, codes)

    async def get_kline(self, code, period, count):
        return await BaseAdapter.get_kline(self, code, period, count)

    async def get_fundamental(self, code):
        return await BaseAdapter.get_fundamental(self, code)

    async def get_news(self, code, limit):
        return await BaseAdapter.get_news(self, code, limit)


@pytest.mark.asyncio
async def test_base_adapter_abstract_methods_raise():
    """子类的"薄包装"调用 super() 抽象方法时, 走 NotImplementedError 抛点."""
    a = _BaseCallingAdapter()
    with pytest.raises(NotImplementedError):
        await a.get_realtime_quote(["600519"])
    with pytest.raises(NotImplementedError):
        await a.get_kline("600519", "1d", 10)
    with pytest.raises(NotImplementedError):
        await a.get_fundamental("600519")
    with pytest.raises(NotImplementedError):
        await a.get_news("600519", 10)
