"""Tencent K线 真实数据集成测

需要 RUN_TENCENT_TESTS=1 启用, 默认 skip.
国内访问 web.ifzq.gtimg.cn 稳, 不需代理.
**注意**: 港美股腾讯 K线只给有限行数 (美股只 2 行), A 股正常.
"""

import os

import pytest

from stock_mcp.adapters.tencent import TencentAdapter

pytestmark = pytest.mark.skipif(
    os.environ.get("RUN_TENCENT_TESTS") != "1",
    reason="tencent 集成测需 RUN_TENCENT_TESTS=1 (CI 跳过避免网络)",
)


@pytest.mark.asyncio
async def test_kline_a_stock_600519():
    """A 股 茅台 600519 K线"""
    a = TencentAdapter()
    try:
        klines = await a.get_kline("600519", "1d", 5, market="a_stock")
    except Exception as e:
        pytest.skip(f"tencent 端不通: {type(e).__name__}: {e}")
    assert len(klines) >= 1
    last = klines[-1]
    assert last.code == "600519"
    assert last.close > 0
    assert last.market == "a_stock"
    print(f"tencent A股 600519 K线: {last.datetime.date()} close={last.close}")


@pytest.mark.asyncio
async def test_kline_hk_00700():
    """港股 腾讯 00700 K线"""
    a = TencentAdapter()
    try:
        klines = await a.get_kline("00700", "1d", 5, market="hk")
    except Exception as e:
        pytest.skip(f"tencent 端不通: {type(e).__name__}: {e}")
    assert len(klines) >= 1
    last = klines[-1]
    assert last.code == "00700"
    assert last.close > 0
    assert last.market == "hk"
    print(f"tencent 港股 00700 K线: {last.datetime.date()} close={last.close}")


@pytest.mark.asyncio
async def test_kline_us_aapl():
    """美股 苹果 AAPL K线 (腾讯美股只给 2 行)"""
    a = TencentAdapter()
    try:
        klines = await a.get_kline("AAPL", "1d", 5, market="us")
    except Exception as e:
        pytest.skip(f"tencent 端不通: {type(e).__name__}: {e}")
    # 腾讯美股 K线只给 2 行 (1 个历史 + 最近 1)
    assert len(klines) >= 1
    last = klines[-1]
    assert last.code == "AAPL"
    assert last.close > 0
    assert last.market == "us"
    print(f"tencent 美股 AAPL K线: {last.datetime.date()} close={last.close}")


@pytest.mark.asyncio
async def test_realtime_a_stock_600519():
    """A 股 茅台 600519 实时"""
    a = TencentAdapter()
    try:
        quotes = await a.get_realtime_quote(["600519"], market="a_stock")
    except Exception as e:
        pytest.skip(f"tencent 端不通: {type(e).__name__}: {e}")
    assert len(quotes) == 1
    q = quotes[0]
    assert q.code == "600519"
    assert q.price > 0
    assert q.market == "a_stock"
    print(f"tencent A股 600519 实时: name={q.name} price={q.price} chg={q.change_pct}%")
