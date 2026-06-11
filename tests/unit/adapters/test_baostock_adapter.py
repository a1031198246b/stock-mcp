"""baostock 适配器单测 (mock baostock 库)"""

import sys
from unittest.mock import MagicMock

import pandas as pd
import pytest

from stock_mcp.domain.errors import DataSourceError


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
    fake_baostock.query_history_k_data_plus.return_value = pd.DataFrame(
        {
            "date": ["2026-06-09", "2026-06-10", "2026-06-11"],
            "open": [100.0, 102.0, 105.0],
            "high": [105.0, 106.0, 108.0],
            "low": [99.0, 101.0, 104.0],
            "close": [103.0, 104.0, 107.0],
            "volume": [10000, 12000, 15000],
            "amount": [1e7, 1.2e7, 1.5e7],
        }
    )

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

    # 模拟 query_profit_data 接收 year/quarter 参数 (新逻辑)
    fake_baostock.query_profit_data.return_value = pd.DataFrame(
        {
            "code": ["sh600519"] * 3,
            "pubDate": ["2024-03-31", "2023-12-31", "2023-09-30"],
            "statDate": ["2024-03-31", "2023-12-31", "2023-09-30"],
            "roeAvg": [0.10, 0.08, 0.07],
            "npMargin": [0.45, 0.40, 0.42],
        }
    )

    a = BaostockAdapter()
    a.initialize()
    stmt = await a.get_financial_statement("600519", "income", market="a_stock")
    assert stmt.code == "600519"
    assert stmt.statement_type == "income"
    assert stmt.market == "a_stock"
    assert stmt.data["roeAvg"][0] == pytest.approx(0.10)
    # 验证调用时带了 year/quarter 参数
    assert fake_baostock.query_profit_data.call_count >= 1
    first_call = fake_baostock.query_profit_data.call_args_list[0]
    assert "year" in first_call.kwargs, "必须传 year 参数 (修复后)"
    assert "quarter" in first_call.kwargs, "必须传 quarter 参数 (修复后)"


@pytest.mark.asyncio
async def test_get_financial_statement_invalid_type_raises(monkeypatch, fake_baostock):
    monkeypatch.setenv("TDX_PATH", "C:/fake/tdx")
    from stock_mcp.adapters.baostock_source import BaostockAdapter

    a = BaostockAdapter()
    a.initialize()
    with pytest.raises(ValueError, match="statement_type"):
        await a.get_financial_statement("600519", "invalid", market="a_stock")


@pytest.mark.asyncio
async def test_get_financial_statement_returns_empty_when_no_data(monkeypatch, fake_baostock):
    """5 个 quarter 都拿不到数据 (新股票/退市) → 返回空 data (不抛)"""
    monkeypatch.setenv("TDX_PATH", "C:/fake/tdx")
    from stock_mcp.adapters.baostock_source import BaostockAdapter

    fake_baostock.query_profit_data.return_value = pd.DataFrame()  # 永远空

    a = BaostockAdapter()
    a.initialize()
    stmt = await a.get_financial_statement("999999", "income", market="a_stock")
    assert stmt.code == "999999"
    assert stmt.data == {}  # 空
    # 应该试了 5 次
    assert fake_baostock.query_profit_data.call_count == 5


@pytest.mark.asyncio
async def test_get_financial_statement_finds_latest_quarter(monkeypatch, fake_baostock):
    """最近 2 quarter 都没数据, 第三个有 → 拿到 1 行不放弃"""
    monkeypatch.setenv("TDX_PATH", "C:/fake/tdx")

    from stock_mcp.adapters.baostock_source import BaostockAdapter

    # 只让 (2025, 2) 那个 quarter 返回非空
    def fake_query_profit(code, year, quarter):
        if (year, quarter) == (2025, 2):
            return pd.DataFrame(
                {"code": ["sh600519"], "statDate": ["2025-06-30"], "roeAvg": [0.10]}
            )
        return pd.DataFrame()

    fake_baostock.query_profit_data.side_effect = fake_query_profit

    a = BaostockAdapter()
    a.initialize()
    stmt = await a.get_financial_statement("600519", "income", market="a_stock")
    assert len(stmt.data) > 0
    assert stmt.data["roeAvg"][0] == pytest.approx(0.10)
    assert fake_baostock.query_profit_data.call_count >= 3  # 至少试了 3 次


def test_coerce_df_fallback_when_get_data_raises_attribute_error():
    """**关键 workaround**: baostock 0.9.20 + pandas 2.x 调 .get_data() 抛 AttributeError.
    应当回退到 rs.data (list of lists) + rs.fields 构造 DataFrame.
    """
    from stock_mcp.adapters.baostock_source import _coerce_df

    # 模拟 pandas 2.x 删了 DataFrame.append
    class FakeResultData:
        error_code = "0"
        fields = ["date", "open", "close"]
        data = [["2026-06-09", "100.0", "105.0"], ["2026-06-10", "102.0", "107.0"]]

        def get_data(self):
            raise AttributeError(
                "'DataFrame' object has no attribute 'append'"
            )  # 模拟 baostock 内部调用 df.append

    rs = FakeResultData()
    df = _coerce_df(rs)
    assert len(df) == 2
    assert list(df.columns) == ["date", "open", "close"]
    assert df.iloc[0]["date"] == "2026-06-09"
    assert df.iloc[1]["close"] == "107.0"


def test_coerce_df_prefers_get_data_when_works():
    """get_data() 正常工作时优先用它 (不触发 fallback)"""
    from stock_mcp.adapters.baostock_source import _coerce_df

    expected_df = pd.DataFrame({"a": [1, 2], "b": [3, 4]})

    class FakeResultData:
        def get_data(self):
            return expected_df

    df = _coerce_df(FakeResultData())
    assert df is expected_df  # 同一个对象, 没用 fallback


def test_coerce_df_handles_dataframe_input():
    """已经是 DataFrame 直接返回"""
    from stock_mcp.adapters.baostock_source import _coerce_df

    df_in = pd.DataFrame({"x": [1]})
    assert _coerce_df(df_in) is df_in


def test_coerce_df_handles_unknown_input():
    """未知输入 (既不是 DataFrame 也没 get_data) → 空 DataFrame"""
    from stock_mcp.adapters.baostock_source import _coerce_df

    df = _coerce_df("garbage")
    assert isinstance(df, pd.DataFrame)
    assert df.empty
