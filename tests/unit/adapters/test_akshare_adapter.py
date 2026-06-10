import pytest
from unittest.mock import patch
import pandas as pd
from stock_mcp.adapters.akshare_source import AkshareAdapter


@pytest.fixture
def mock_akshare():
    with patch("stock_mcp.adapters.akshare_source.ak") as mock_ak:
        yield mock_ak


@pytest.mark.asyncio
async def test_get_fundamental_a_share(mock_akshare):
    mock_akshare.stock_a_indicator_lg.return_value = pd.DataFrame({
        "code": ["600519"],
        "pe": [25.5],
        "pb": [8.2],
        "总股本": [12.56],   # 亿
        "总市值": [18840.0],  # 亿
    })
    a = AkshareAdapter()
    fund = await a.get_fundamental("600519")
    assert fund is not None
    assert fund.pe == 25.5
    assert fund.source == "akshare"


@pytest.mark.asyncio
async def test_get_kline_daily(mock_akshare):
    mock_akshare.stock_zh_a_hist.return_value = pd.DataFrame({
        "日期": ["2026-06-10", "2026-06-09"],
        "开盘": [100, 99],
        "最高": [105, 102],
        "最低": [99, 98],
        "收盘": [103, 100],
        "成交量": [1000, 1500],
        "成交额": [1e7, 1.5e7],
    })
    a = AkshareAdapter()
    klines = await a.get_kline("600519", "1d", 2)
    assert len(klines) == 2
    assert klines[0].close == 103


@pytest.mark.asyncio
async def test_get_fundamental_handles_empty(mock_akshare):
    mock_akshare.stock_a_indicator_lg.return_value = pd.DataFrame()
    a = AkshareAdapter()
    fund = await a.get_fundamental("600519")
    assert fund is None


@pytest.mark.asyncio
async def test_get_realtime_quote_returns_empty_akshare_not_ideal(mock_akshare):
    """akshare 不擅长实时行情, 直接返回空"""
    a = AkshareAdapter()
    quotes = await a.get_realtime_quote(["600519"])
    assert quotes == []
