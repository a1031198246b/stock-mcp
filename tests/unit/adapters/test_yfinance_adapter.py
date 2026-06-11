"""yfinance 适配器单测 (mock yfinance 库)"""

import sys
from unittest.mock import MagicMock

import pandas as pd
import pytest


class FakeYfModule:
    def __init__(self):
        self.Ticker = MagicMock()
        self.download = MagicMock()


@pytest.fixture
def fake_yfinance(monkeypatch):
    fake = FakeYfModule()
    sys.modules["yfinance"] = fake
    yield fake
    sys.modules.pop("yfinance", None)


def test_initialize_enabled_when_yfinance_installed(monkeypatch, fake_yfinance):
    """yfinance 装着 → enabled=True, supported_markets 含 hk/us"""
    monkeypatch.setenv("TDX_PATH", "C:/fake/tdx")
    from stock_mcp.adapters.yfinance_source import YfinanceAdapter

    a = YfinanceAdapter()
    a.initialize()
    assert a.enabled is True
    assert "hk" in a.supported_markets
    assert "us" in a.supported_markets
    assert "a_stock" not in a.supported_markets  # 不服务 A 股


def test_initialize_disabled_when_yfinance_not_installed(monkeypatch):
    # 使 `import yfinance` 抛 ImportError (sys.modules 设为 None 是 Python 标准做法)
    monkeypatch.setitem(sys.modules, "yfinance", None)
    monkeypatch.setenv("TDX_PATH", "C:/fake/tdx")
    from stock_mcp.adapters.yfinance_source import YfinanceAdapter

    a = YfinanceAdapter()
    a.initialize()
    assert a.enabled is False


@pytest.mark.asyncio
async def test_hk_code_pads_to_4_digits(monkeypatch, fake_yfinance):
    """港股代码 '00700' → yfinance '0700.HK' (5位补0)"""
    monkeypatch.setenv("TDX_PATH", "C:/fake/tdx")
    from stock_mcp.adapters.yfinance_source import YfinanceAdapter

    # yfinance.Ticker("0700.HK").fast_info 返回 NamedTuple-like
    fake_yfinance.Ticker.return_value.fast_info.last_price = 350.0
    fake_yfinance.Ticker.return_value.fast_info.previous_close = 340.0
    fake_yfinance.Ticker.return_value.fast_info.currency = "HKD"

    a = YfinanceAdapter()
    a.initialize()
    quotes = await a.get_realtime_quote(["00700"], market="hk")
    assert len(quotes) == 1
    assert quotes[0].code == "00700"
    assert quotes[0].market == "hk"
    # 验证 Ticker 是用 "0700.HK" 调的
    fake_yfinance.Ticker.assert_called_with("0700.HK")


@pytest.mark.asyncio
async def test_us_code_passthrough(monkeypatch, fake_yfinance):
    """美股代码 'AAPL' 直接传给 yfinance (无需转换)"""
    monkeypatch.setenv("TDX_PATH", "C:/fake/tdx")
    from stock_mcp.adapters.yfinance_source import YfinanceAdapter

    fake_yfinance.Ticker.return_value.fast_info.last_price = 200.0
    fake_yfinance.Ticker.return_value.fast_info.previous_close = 195.0
    fake_yfinance.Ticker.return_value.fast_info.currency = "USD"

    a = YfinanceAdapter()
    a.initialize()
    quotes = await a.get_realtime_quote(["AAPL"], market="us")
    assert len(quotes) == 1
    assert quotes[0].code == "AAPL"
    assert quotes[0].market == "us"
    fake_yfinance.Ticker.assert_called_with("AAPL")


@pytest.mark.asyncio
async def test_a_stock_market_raises_value_error(monkeypatch, fake_yfinance):
    """yfinance 不服务 A 股, 显式 raise (上层不该路由过来)"""
    monkeypatch.setenv("TDX_PATH", "C:/fake/tdx")
    from stock_mcp.adapters.yfinance_source import YfinanceAdapter

    a = YfinanceAdapter()
    a.initialize()
    with pytest.raises(ValueError, match="a_stock"):
        await a.get_realtime_quote(["600519"], market="a_stock")


@pytest.mark.asyncio
async def test_get_kline_hk(monkeypatch, fake_yfinance):
    """yfinance K线 — 港股, 内部 yf.Ticker(...).history()"""
    monkeypatch.setenv("TDX_PATH", "C:/fake/tdx")
    from stock_mcp.adapters.yfinance_source import YfinanceAdapter

    history_df = pd.DataFrame(
        {
            "Date": pd.to_datetime(["2026-06-09", "2026-06-10", "2026-06-11"]),
            "Open": [340.0, 345.0, 350.0],
            "High": [355.0, 358.0, 360.0],
            "Low": [338.0, 342.0, 348.0],
            "Close": [350.0, 355.0, 358.0],
            "Volume": [1000000, 1100000, 1200000],
        }
    )
    fake_yfinance.Ticker.return_value.history.return_value = history_df

    a = YfinanceAdapter()
    a.initialize()
    klines = await a.get_kline("00700", "1d", 3, market="hk")
    assert len(klines) == 3
    assert klines[0].close == 350.0
    assert klines[0].market == "hk"
    fake_yfinance.Ticker.assert_called_with("0700.HK")
    # history 调用的 period/interval 参数
    call = fake_yfinance.Ticker.return_value.history.call_args
    assert call.kwargs.get("period") == "3mo" or "1d" in str(call)


@pytest.mark.asyncio
async def test_get_fundamental_from_info(monkeypatch, fake_yfinance):
    """yfinance .info 提取 PE/PB/ROE/marketCap"""
    monkeypatch.setenv("TDX_PATH", "C:/fake/tdx")
    from stock_mcp.adapters.yfinance_source import YfinanceAdapter

    fake_yfinance.Ticker.return_value.info = {
        "shortName": "Apple Inc.",
        "trailingPE": 30.5,
        "priceToBook": 45.2,
        "returnOnEquity": 1.5,  # 150%? yfinance 实际是 0.015
        "marketCap": 3_000_000_000_000,
        "currency": "USD",
    }

    a = YfinanceAdapter()
    a.initialize()
    f = await a.get_fundamental("AAPL", market="us")
    assert f is not None
    assert f.code == "AAPL"
    assert f.name == "Apple Inc."
    assert f.pe == pytest.approx(30.5)
    assert f.pb == pytest.approx(45.2)
    assert f.market_cap == pytest.approx(3e12 / 1e8)  # 我们的单位是亿元
    assert f.market == "us"


@pytest.mark.asyncio
async def test_get_news_returns_empty_or_list(monkeypatch, fake_yfinance):
    """yfinance .news 返回 list 或空 list"""
    monkeypatch.setenv("TDX_PATH", "C:/fake/tdx")
    from stock_mcp.adapters.yfinance_source import YfinanceAdapter

    fake_yfinance.Ticker.return_value.news = []
    a = YfinanceAdapter()
    a.initialize()
    news = await a.get_news("AAPL", 5, market="us")
    assert news == []
