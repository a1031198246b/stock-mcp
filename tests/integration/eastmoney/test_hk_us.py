"""eastmoney 港美股 真实数据集成测

需要 RUN_EASTMONEY_TESTS=1 启用, 默认 skip.
eastmoney 国内访问稳, 不需要代理. 但端点偶发 502, adapter 已加 3 次重试.
"""

import os

import pytest

from stock_mcp.adapters.eastmoney import EastmoneyAdapter

pytestmark = pytest.mark.skipif(
    os.environ.get("RUN_EASTMONEY_TESTS") != "1",
    reason="eastmoney 集成测需 RUN_EASTMONEY_TESTS=1 (CI 跳过避免网络)",
)


@pytest.mark.asyncio
async def test_realtime_hk_00700():
    """港股 腾讯 00700 实时"""
    a = EastmoneyAdapter()
    try:
        quotes = await a.get_realtime_quote(["00700"], market="hk")
    except Exception as e:
        pytest.skip(f"eastmoney 端不通 (国内偶发): {type(e).__name__}: {e}")
    assert len(quotes) >= 1, "应至少返回腾讯 00700 行情"
    q = quotes[0]
    assert q.code == "00700"
    assert q.price > 0
    assert q.market == "hk"
    print(f"eastmoney 00700 实时: name={q.name} price={q.price} chg={q.change_pct}%")


@pytest.mark.asyncio
async def test_realtime_us_aapl():
    """美股 苹果 AAPL 实时"""
    a = EastmoneyAdapter()
    try:
        quotes = await a.get_realtime_quote(["AAPL"], market="us")
    except Exception as e:
        pytest.skip(f"eastmoney 端不通: {type(e).__name__}: {e}")
    assert len(quotes) >= 1
    q = quotes[0]
    assert q.code == "AAPL"
    assert q.price > 0
    assert q.market == "us"
    print(f"eastmoney AAPL 实时: name={q.name} price={q.price} chg={q.change_pct}%")


@pytest.mark.asyncio
async def test_kline_hk_00700():
    """港股 腾讯 00700 K线 (日, 5 天)"""
    a = EastmoneyAdapter()
    try:
        klines = await a.get_kline("00700", "1d", 5, market="hk")
    except Exception as e:
        pytest.skip(f"eastmoney 端不通: {type(e).__name__}: {e}")
    assert len(klines) >= 1
    last = klines[-1]
    assert last.code == "00700"
    assert last.close > 0
    assert last.market == "hk"
    print(f"eastmoney 00700 K线: 最新 {last.datetime.date()} close={last.close}")


@pytest.mark.asyncio
async def test_kline_us_aapl():
    """美股 苹果 AAPL K线 (日, 5 天)"""
    a = EastmoneyAdapter()
    try:
        klines = await a.get_kline("AAPL", "1d", 5, market="us")
    except Exception as e:
        pytest.skip(f"eastmoney 端不通: {type(e).__name__}: {e}")
    assert len(klines) >= 1
    last = klines[-1]
    assert last.code == "AAPL"
    assert last.close > 0
    assert last.market == "us"
    print(f"eastmoney AAPL K线: 最新 {last.datetime.date()} close={last.close}")
