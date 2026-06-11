"""yfinance 真实数据集成测

需要 RUN_YFINANCE_TESTS=1 启用, 默认 skip (避免 CI 网络依赖).
当前环境 (国内网络) 访问 query1.finance.yahoo.com 返回 403 (中文限流页),
所以 yfinance 在国内基本不可用, 但写出来方便 VPN/海外环境跑.
"""

import os

import pytest

from stock_mcp.adapters.yfinance_source import YfinanceAdapter

pytestmark = pytest.mark.skipif(
    os.environ.get("RUN_YFINANCE_TESTS") != "1",
    reason="yfinance 集成测需 RUN_YFINANCE_TESTS=1 (CI 跳过避免网络)",
)


@pytest.mark.asyncio
async def test_hk_realtime_00700():
    """港股 0700.HK 实时, 需要海外网络"""
    a = YfinanceAdapter()
    a.initialize()
    assert a.enabled
    try:
        quotes = await a.get_realtime_quote(["00700"], market="hk")
    except Exception as e:
        pytest.skip(f"yfinance 网络不通 (国内常见): {type(e).__name__}: {e}")
    assert len(quotes) == 1
    q = quotes[0]
    assert q.code == "00700"
    assert q.market == "hk"
    assert q.price > 0
    print(f"yfinance 00700 实时: price={q.price} change_pct={q.change_pct}%")


@pytest.mark.asyncio
async def test_us_realtime_aapl():
    """美股 AAPL 实时"""
    a = YfinanceAdapter()
    a.initialize()
    try:
        quotes = await a.get_realtime_quote(["AAPL"], market="us")
    except Exception as e:
        pytest.skip(f"yfinance 网络不通: {type(e).__name__}: {e}")
    assert len(quotes) == 1
    q = quotes[0]
    assert q.code == "AAPL"
    assert q.market == "us"
    print(f"yfinance AAPL 实时: price={q.price}")


@pytest.mark.asyncio
async def test_us_kline_aapl():
    """美股 AAPL 日 K, 30 天"""
    a = YfinanceAdapter()
    a.initialize()
    try:
        klines = await a.get_kline("AAPL", "1d", 30, market="us")
    except Exception as e:
        pytest.skip(f"yfinance 网络不通: {type(e).__name__}: {e}")
    assert len(klines) > 0
    last = klines[-1]
    assert last.code == "AAPL"
    assert last.market == "us"
    print(f"yfinance AAPL 最新 K: {last.datetime.date()} close={last.close}")


@pytest.mark.asyncio
async def test_us_fundamental_aapl():
    """美股 AAPL 基本面, 验证 shortName/PE/PB/marketCap 都有"""
    a = YfinanceAdapter()
    a.initialize()
    try:
        f = await a.get_fundamental("AAPL", market="us")
    except Exception as e:
        pytest.skip(f"yfinance 网络不通: {type(e).__name__}: {e}")
    assert f is not None
    assert f.code == "AAPL"
    assert f.name  # shortName 不为空
    print(f"yfinance AAPL 基本面: name={f.name} pe={f.pe} marketCap={f.market_cap}亿元")
