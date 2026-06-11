"""baostock 适配器单测 (mock baostock 库)"""
import sys
from datetime import datetime
from unittest.mock import MagicMock

import pandas as pd
import pytest

from stock_mcp.domain.errors import DataSourceError
from stock_mcp.domain.models import Kline


class FakeBsModule:
    """模拟 baostock 模块"""
    def __init__(self):
        self.login = MagicMock(return_value=None)  # ContextManager
        self.logout = MagicMock(return_value=None)
        self.query_history_k_data_plus = MagicMock()
        self.query_profit_data = MagicMock()
        self.query_balance_data = MagicMock()
        self.query_cash_flow_data = MagicMock()
        self.query_stock_industry = MagicMock()


@pytest.fixture
def fake_baostock(monkeypatch):
    fake = FakeBsModule()
    sys.modules["baostock"] = fake
    yield fake
    sys.modules.pop("baostock", None)


def test_initialize_enabled_when_baostock_installed(monkeypatch, fake_baostock):
    """baostock 装着 + login 成功 → enabled=True"""
    monkeypatch.setenv("TDX_PATH", "C:/fake/tdx")
    from stock_mcp.adapters.baostock_source import BaostockAdapter
    a = BaostockAdapter()
    a.initialize()
    assert a.enabled is True
    assert a.supported_markets == ["a_stock"]


def test_initialize_disabled_when_baostock_not_installed(monkeypatch):
    """baostock 没装 → enabled=False"""
    # 使 `import baostock` 抛 ImportError (sys.modules 设为 None 是 Python 标准做法)
    monkeypatch.setitem(sys.modules, "baostock", None)
    monkeypatch.setenv("TDX_PATH", "C:/fake/tdx")
    from stock_mcp.adapters.baostock_source import BaostockAdapter
    a = BaostockAdapter()
    a.initialize()
    assert a.enabled is False


@pytest.mark.asyncio
async def test_get_realtime_quote_raises(monkeypatch, fake_baostock):
    """baostock 无实时行情, 显式 raise (上层 fallback 到 tqcenter/sina)"""
    monkeypatch.setenv("TDX_PATH", "C:/fake/tdx")
    from stock_mcp.adapters.baostock_source import BaostockAdapter
    a = BaostockAdapter()
    a.initialize()
    with pytest.raises(DataSourceError):
        await a.get_realtime_quote(["600519"], market="a_stock")


@pytest.mark.asyncio
async def test_get_kline_normalizes_baostock_dataframe(monkeypatch, fake_baostock):
    """baostock K线 DataFrame → List[Kline]"""
    monkeypatch.setenv("TDX_PATH", "C:/fake/tdx")
    from stock_mcp.adapters.baostock_source import BaostockAdapter

    # baostock 返回 DataFrame with columns: date, open, high, low, close, volume, amount
    fake_baostock.query_history_k_data_plus.return_value = pd.DataFrame({
        "date": ["2026-06-09", "2026-06-10", "2026-06-11"],
        "open": [100.0, 102.0, 105.0],
        "high": [105.0, 106.0, 108.0],
        "low": [99.0, 101.0, 104.0],
        "close": [103.0, 104.0, 107.0],
        "volume": [10000, 12000, 15000],
        "amount": [1e7, 1.2e7, 1.5e7],
    })

    a = BaostockAdapter()
    a.initialize()
    klines = await a.get_kline("600519", "1d", 3, market="a_stock")
    assert len(klines) == 3
    assert klines[0].code == "600519"
    assert klines[0].close == 103.0
    assert klines[0].market == "a_stock"


@pytest.mark.asyncio
async def test_get_fundamental_raises_not_implemented(monkeypatch, fake_baostock):
    """基本面走 get_financial_statement, 此方法抛 NotImplementedError"""
    monkeypatch.setenv("TDX_PATH", "C:/fake/tdx")
    from stock_mcp.adapters.baostock_source import BaostockAdapter
    a = BaostockAdapter()
    a.initialize()
    with pytest.raises(NotImplementedError):
        await a.get_fundamental("600519", market="a_stock")


@pytest.mark.asyncio
async def test_get_news_raises_not_implemented(monkeypatch, fake_baostock):
    monkeypatch.setenv("TDX_PATH", "C:/fake/tdx")
    from stock_mcp.adapters.baostock_source import BaostockAdapter
    a = BaostockAdapter()
    a.initialize()
    with pytest.raises(NotImplementedError):
        await a.get_news("600519", 10, market="a_stock")


@pytest.mark.asyncio
async def test_get_financial_statement_income(monkeypatch, fake_baostock):
    """baostock 利润表 (income) — 仅 baostock 实现"""
    monkeypatch.setenv("TDX_PATH", "C:/fake/tdx")
    from stock_mcp.adapters.baostock_source import BaostockAdapter

    fake_baostock.query_profit_data.return_value = pd.DataFrame({
        "code": ["sh600519"] * 3,
        "pubDate": ["2024-03-31", "2023-12-31", "2023-09-30"],
        "statDate": ["2024-03-31", "2023-12-31", "2023-09-30"],
        "roeAvg": [0.10, 0.08, 0.07],
        "npMargin": [0.45, 0.40, 0.42],
    })

    a = BaostockAdapter()
    a.initialize()
    stmt = await a.get_financial_statement("600519", "income", market="a_stock")
    assert stmt.code == "600519"
    assert stmt.statement_type == "income"
    assert stmt.market == "a_stock"
    assert stmt.data["roeAvg"][0] == pytest.approx(0.10)


@pytest.mark.asyncio
async def test_get_financial_statement_invalid_type_raises(monkeypatch, fake_baostock):
    monkeypatch.setenv("TDX_PATH", "C:/fake/tdx")
    from stock_mcp.adapters.baostock_source import BaostockAdapter
    a = BaostockAdapter()
    a.initialize()
    with pytest.raises(ValueError, match="statement_type"):
        await a.get_financial_statement("600519", "invalid", market="a_stock")
