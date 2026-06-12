import sys
from unittest.mock import MagicMock

import pandas as pd
import pytest

from stock_mcp.adapters.akshare_source import AkshareAdapter, _safe_float
from stock_mcp.domain.errors import DataSourceError


class FakeAkModule:
    """模拟 akshare 模块 — 暴露常用 stock_*/fund_*/news_* 函数"""

    def __init__(self):
        # 关键接口都做成 MagicMock, 允许在测试里指定 return_value/side_effect
        self.stock_zh_a_hist = MagicMock()
        self.stock_a_indicator_lg = MagicMock()
        self.stock_news_em = MagicMock()


@pytest.fixture
def fake_akshare(monkeypatch):
    fake = FakeAkModule()
    sys.modules["akshare"] = fake
    # 重新载入模块, 让模块顶部的 `import akshare as ak` 拿到我们的 fake
    import importlib

    import stock_mcp.adapters.akshare_source as akshare_mod

    importlib.reload(akshare_mod)
    # 同步调整类属性
    akshare_mod.AkshareAdapter.enabled = True
    yield fake, akshare_mod
    sys.modules.pop("akshare", None)
    importlib.reload(akshare_mod)
    akshare_mod.AkshareAdapter.enabled = akshare_mod.ak is not None


# ============== get_kline 测试 ==============


@pytest.mark.asyncio
async def test_get_kline_daily(fake_akshare):
    fake, akshare_mod = fake_akshare
    fake.stock_zh_a_hist.return_value = pd.DataFrame(
        {
            "日期": ["2026-06-10", "2026-06-09"],
            "开盘": [100, 99],
            "最高": [105, 102],
            "最低": [99, 98],
            "收盘": [103, 100],
            "成交量": [1000, 1500],
            "成交额": [1e7, 1.5e7],
        }
    )
    a = akshare_mod.AkshareAdapter()
    klines = await a.get_kline("600519", "1d", 2)
    assert len(klines) == 2
    assert klines[0].close == 103
    assert klines[0].code == "600519"
    assert klines[0].source == "akshare"


@pytest.mark.asyncio
async def test_get_kline_weekly(fake_akshare):
    """period=1w → ak.stock_zh_a_hist 的 period 参数应为 weekly"""
    fake, akshare_mod = fake_akshare
    fake.stock_zh_a_hist.return_value = pd.DataFrame(
        {
            "日期": ["2026-06-05"],
            "开盘": [100],
            "最高": [110],
            "最低": [95],
            "收盘": [105],
            "成交量": [5000],
            "成交额": [5e7],
        }
    )
    a = akshare_mod.AkshareAdapter()
    await a.get_kline("600519", "1w", 1)
    fake.stock_zh_a_hist.assert_called_once_with(
        symbol="600519", period="weekly", adjust="qfq", count=1
    )


@pytest.mark.asyncio
async def test_get_kline_monthly(fake_akshare):
    """period=1M → ak.stock_zh_a_hist 的 period 参数应为 monthly"""
    fake, akshare_mod = fake_akshare
    fake.stock_zh_a_hist.return_value = pd.DataFrame(
        {
            "日期": ["2026-05-31"],
            "开盘": [100],
            "最高": [110],
            "最低": [95],
            "收盘": [105],
            "成交量": [5000],
            "成交额": [5e7],
        }
    )
    a = akshare_mod.AkshareAdapter()
    await a.get_kline("600519", "1M", 1)
    fake.stock_zh_a_hist.assert_called_once_with(
        symbol="600519", period="monthly", adjust="qfq", count=1
    )


@pytest.mark.asyncio
async def test_get_kline_unknown_period_defaults_to_daily(fake_akshare):
    """未识别 period (如 1m/5m) → 默认 daily"""
    fake, akshare_mod = fake_akshare
    fake.stock_zh_a_hist.return_value = pd.DataFrame(
        {
            "日期": ["2026-06-10"],
            "开盘": [100],
            "最高": [110],
            "最低": [95],
            "收盘": [105],
            "成交量": [5000],
            "成交额": [5e7],
        }
    )
    a = akshare_mod.AkshareAdapter()
    await a.get_kline("600519", "1m", 1)
    # 1m 不在 mapping 里 → 兜底 daily
    assert fake.stock_zh_a_hist.call_args.kwargs["period"] == "daily"


@pytest.mark.asyncio
async def test_get_kline_raises_on_exception(fake_akshare):
    """akshare API 抛错 → 包装成 DataSourceError"""
    fake, akshare_mod = fake_akshare
    fake.stock_zh_a_hist.side_effect = RuntimeError("network down")
    a = akshare_mod.AkshareAdapter()
    with pytest.raises(DataSourceError) as exc_info:
        await a.get_kline("600519", "1d", 5)
    assert "network down" in str(exc_info.value)
    assert exc_info.value.source == "akshare"


@pytest.mark.asyncio
async def test_get_kline_raises_when_akshare_not_installed(monkeypatch):
    """akshare 未装时 get_kline 抛 DataSourceError (不调用底层)"""
    import stock_mcp.adapters.akshare_source as akshare_mod

    monkeypatch.setattr(akshare_mod, "ak", None)
    a = akshare_mod.AkshareAdapter()
    with pytest.raises(DataSourceError) as exc_info:
        await a.get_kline("600519", "1d", 5)
    assert "未安装" in str(exc_info.value)


# ============== get_fundamental 测试 ==============


@pytest.mark.asyncio
async def test_get_fundamental_a_share(fake_akshare):
    fake, akshare_mod = fake_akshare
    fake.stock_a_indicator_lg.return_value = pd.DataFrame(
        {
            "code": ["600519"],
            "pe": [25.5],
            "pb": [8.2],
            "总股本": [12.56],  # 亿
            "总市值": [18840.0],  # 亿
        }
    )
    a = akshare_mod.AkshareAdapter()
    fund = await a.get_fundamental("600519")
    assert fund is not None
    assert fund.pe == 25.5
    assert fund.pb == 8.2
    assert fund.total_shares == 12.56
    assert fund.market_cap == 18840.0
    assert fund.source == "akshare"


@pytest.mark.asyncio
async def test_get_fundamental_handles_empty(fake_akshare):
    """空 DataFrame → 返回 None (不抛)"""
    fake, akshare_mod = fake_akshare
    fake.stock_a_indicator_lg.return_value = pd.DataFrame()
    a = akshare_mod.AkshareAdapter()
    fund = await a.get_fundamental("600519")
    assert fund is None


@pytest.mark.asyncio
async def test_get_fundamental_handles_nan_fields(fake_akshare):
    """PE/PB 等字段为 NaN → _safe_float 应返回 None"""
    fake, akshare_mod = fake_akshare
    fake.stock_a_indicator_lg.return_value = pd.DataFrame(
        {
            "pe": [float("nan")],
            "pb": [None],
            "总股本": [12.56],
            "总市值": [18840.0],
        }
    )
    a = akshare_mod.AkshareAdapter()
    fund = await a.get_fundamental("600519")
    assert fund is not None
    assert fund.pe is None
    assert fund.pb is None
    assert fund.total_shares == 12.56


@pytest.mark.asyncio
async def test_get_fundamental_raises_on_exception(fake_akshare):
    """akshare 抛错 → 包装成 DataSourceError"""
    fake, akshare_mod = fake_akshare
    fake.stock_a_indicator_lg.side_effect = RuntimeError("api drift")
    a = akshare_mod.AkshareAdapter()
    with pytest.raises(DataSourceError) as exc_info:
        await a.get_fundamental("600519")
    assert "api drift" in str(exc_info.value)


@pytest.mark.asyncio
async def test_get_fundamental_raises_when_akshare_not_installed(monkeypatch):
    """akshare 未装时 get_fundamental 抛 DataSourceError"""
    import stock_mcp.adapters.akshare_source as akshare_mod

    monkeypatch.setattr(akshare_mod, "ak", None)
    a = akshare_mod.AkshareAdapter()
    with pytest.raises(DataSourceError) as exc_info:
        await a.get_fundamental("600519")
    assert "未安装" in str(exc_info.value)


# ============== get_news 测试 ==============


@pytest.mark.asyncio
async def test_get_news_returns_empty_list(fake_akshare):
    """akshare 当前不做新闻 (P3 阶段), 即使调用成功也返回 []"""
    fake, akshare_mod = fake_akshare
    fake.stock_news_em.return_value = ["some news"]
    a = akshare_mod.AkshareAdapter()
    news = await a.get_news("600519", 10)
    assert news == []


@pytest.mark.asyncio
async def test_get_news_returns_empty_when_akshare_not_installed(monkeypatch):
    """akshare 未装时 get_news 不抛错, 直接返回 [] (兼容降级)"""
    import stock_mcp.adapters.akshare_source as akshare_mod

    monkeypatch.setattr(akshare_mod, "ak", None)
    a = akshare_mod.AkshareAdapter()
    news = await a.get_news("600519", 10)
    assert news == []


@pytest.mark.asyncio
async def test_get_news_raises_on_exception(fake_akshare):
    """akshare 抛错 → 包装成 DataSourceError (注意: get_news 用 raise 不用 return [])"""
    fake, akshare_mod = fake_akshare
    fake.stock_news_em.side_effect = RuntimeError("api changed")
    a = akshare_mod.AkshareAdapter()
    with pytest.raises(DataSourceError) as exc_info:
        await a.get_news("600519", 10)
    assert "api changed" in str(exc_info.value)


# ============== get_realtime_quote 测试 ==============


@pytest.mark.asyncio
async def test_get_realtime_quote_returns_empty(fake_akshare):
    """akshare 不擅长实时行情, 让位给 tqcenter / sina"""
    fake, akshare_mod = fake_akshare
    a = akshare_mod.AkshareAdapter()
    quotes = await a.get_realtime_quote(["600519", "000001"])
    assert quotes == []


# ============== 通用属性 / 边界测试 ==============


def test_adapter_name_and_priority():
    """name/priority 应当固定"""
    a = AkshareAdapter()
    assert a.name == "akshare"
    assert a.priority == 4  # 2026-06-12 priority 重分配


def test_safe_float_normal_values():
    """_safe_float: 正常数值"""
    assert _safe_float(1.5) == 1.5
    assert _safe_float("2.5") == 2.5
    assert _safe_float(0) == 0.0


def test_safe_float_nan_returns_none():
    """_safe_float: NaN → None (不是 0)"""
    assert _safe_float(float("nan")) is None
    assert _safe_float(None) is None


def test_safe_float_invalid_returns_none():
    """_safe_float: 无法转 float → None (不抛)"""
    assert _safe_float("not a number") is None
    assert _safe_float(object()) is None
    assert _safe_float([1, 2, 3]) is None
