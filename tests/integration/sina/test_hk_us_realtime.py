"""Sina 港美股 真实数据集成测

需要 RUN_SINA_TESTS=1 启用, 默认 skip.
国内访问 hq.sinajs.cn 稳, 不需代理.
**注意**: 港美股**盘前/盘后** sina 字段可能错位 (字段不可靠), 推荐盘中查询.
"""

import os

import pytest

from stock_mcp.adapters.sina import SinaAdapter

pytestmark = pytest.mark.skipif(
    os.environ.get("RUN_SINA_TESTS") != "1",
    reason="sina 集成测需 RUN_SINA_TESTS=1 (CI 跳过避免网络)",
)


@pytest.mark.asyncio
async def test_realtime_hk_00700():
    """港股 腾讯 00700 实时"""
    a = SinaAdapter()
    try:
        quotes = await a.get_realtime_quote(["00700"], market="hk")
    except Exception as e:
        pytest.skip(f"sina 端不通: {type(e).__name__}: {e}")
    assert len(quotes) == 1
    q = quotes[0]
    assert q.code == "00700"
    assert q.name == "腾讯控股"
    assert q.price > 0
    assert q.market == "hk"
    print(f"sina 港股 00700: name={q.name} price={q.price} chg={q.change_pct}%")


@pytest.mark.asyncio
async def test_realtime_us_aapl():
    """美股 苹果 AAPL 实时"""
    a = SinaAdapter()
    try:
        quotes = await a.get_realtime_quote(["AAPL"], market="us")
    except Exception as e:
        pytest.skip(f"sina 端不通: {type(e).__name__}: {e}")
    assert len(quotes) == 1
    q = quotes[0]
    assert q.code == "AAPL"
    assert q.name == "苹果"
    assert q.price > 0
    assert q.market == "us"
    print(f"sina 美股 AAPL: name={q.name} price={q.price} chg={q.change_pct}%")
