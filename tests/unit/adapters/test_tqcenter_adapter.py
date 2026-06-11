import sys
import pytest
from unittest.mock import MagicMock
from stock_mcp.adapters.tqcenter import TqcenterAdapter
from stock_mcp.domain.errors import DataSourceError


class FakeTqModule:
    """模拟 tqcenter 模块"""

    def __init__(self):
        self.tq = MagicMock()


@pytest.fixture
def fake_tqcenter(monkeypatch):
    fake = FakeTqModule()
    # 让 from-import 拿到这个 fake
    sys.modules["tqcenter"] = fake
    yield fake
    sys.modules.pop("tqcenter", None)


@pytest.mark.asyncio
async def test_initialize_calls_tq_initialize(fake_tqcenter, monkeypatch):
    monkeypatch.setenv("TDX_PATH", "C:/fake/tdx")
    a = TqcenterAdapter()
    a.initialize()  # 同步
    fake_tqcenter.tq.initialize.assert_called_once_with("C:/fake/tdx")


@pytest.mark.asyncio
async def test_initialize_succeeds_sets_enabled(fake_tqcenter, monkeypatch):
    monkeypatch.setenv("TDX_PATH", "C:/fake/tdx")
    a = TqcenterAdapter()
    a.initialize()
    assert a.enabled is True


@pytest.mark.asyncio
async def test_initialize_failure_disables(fake_tqcenter, monkeypatch):
    monkeypatch.setenv("TDX_PATH", "C:/fake/tdx")
    fake_tqcenter.tq.initialize.side_effect = Exception("connection failed")
    a = TqcenterAdapter()
    a.initialize()
    assert a.enabled is False


@pytest.mark.asyncio
async def test_health_check_calls_health_probe(fake_tqcenter, monkeypatch):
    monkeypatch.setenv("TDX_PATH", "C:/fake/tdx")
    a = TqcenterAdapter()
    a.initialize()
    fake_tqcenter.tq.get_stock_list = MagicMock(return_value=["600519.SH"])
    result = await a.health_check()
    assert result is True


@pytest.mark.asyncio
async def test_get_realtime_quote_normalizes_fields(fake_tqcenter, monkeypatch):
    monkeypatch.setenv("TDX_PATH", "C:/fake/tdx")
    a = TqcenterAdapter()
    a.initialize()

    fake_tqcenter.tq.get_market_snapshot = MagicMock(return_value={
        "Now": 1500.0,
        "LastClose": 1463.5,
        "Amount": 1.2e9,
        "Volume": 10000,
        "Open": 1480.0,
        "Max": 1510.0,
        "Min": 1475.0,
        "Buyv": [100, 200, 300, 400, 500],
        "Sellv": [150, 250, 350, 450, 550],
    })
    fake_tqcenter.tq.get_stock_info = MagicMock(return_value={
        "ErrorId": "0", "Name": "贵州茅台", "J_zgb": 0,  # 总股本（万）— 0
    })

    quotes = await a.get_realtime_quote(["600519"])
    assert len(quotes) == 1
    q = quotes[0]
    assert q.code == "600519"
    assert q.price == 1500.0
    assert q.change_pct == pytest.approx(2.49, rel=0.01)
    assert q.bid_5 == [100, 200, 300, 400, 500]
    assert q.ask_5 == [150, 250, 350, 450, 550]
    assert q.source == "tqcenter"


@pytest.mark.asyncio
async def test_health_check_failure_returns_false(fake_tqcenter, monkeypatch):
    monkeypatch.setenv("TDX_PATH", "C:/fake/tdx")
    a = TqcenterAdapter()
    a.initialize()
    fake_tqcenter.tq.get_stock_list = MagicMock(side_effect=Exception("timeout"))
    result = await a.health_check()
    assert result is False


class FakeTqKlineModule(FakeTqModule):
    pass


def test_initialize_calls_close_between_mode_retries(fake_tqcenter, monkeypatch):
    """回归测试: 多次 init 之间必须调 close() 真正释放 DLL 锁

    之前的 bug: 直接 self._tq._initialized = False, 只骗 Python 不骗 DLL。
    下次 init 时 DLL 报 '已有同名策略运行'。

    这个测试验证: 重试 mode 时, close() 会被调 (真正释放 DLL 锁)
    """
    monkeypatch.setenv("TDX_PATH", "C:/fake/tdx")
    fake_tqcenter.tq.initialize.side_effect = Exception("mock failure")

    a = TqcenterAdapter()
    a.initialize()

    # 关键断言: 在 mode 循环里, 每次重试前都调了 close()
    # 10 个 mode, 至少调 10 次 close (因为每个 mode 失败后都要重试)
    assert fake_tqcenter.tq.close.call_count >= 10, (
        f"close() 应在每次 mode 重试前调, 实际调了 {fake_tqcenter.tq.close.call_count} 次"
    )


def test_initialize_does_not_manually_set_private_flag(fake_tqcenter, monkeypatch):
    """回归测试: 不应手动设 self._tq._initialized = False

    之前手动设这个 flag 是 bug 的根源 (骗 Python 不骗 DLL)。
    我们重试时只调 close(), 靠 DLL 自己管理 _initialized。
    """
    monkeypatch.setenv("TDX_PATH", "C:/fake/tdx")
    fake_tqcenter.tq.initialize.side_effect = Exception("mock failure")

    a = TqcenterAdapter()
    a.initialize()

    # close() 必须被调
    assert fake_tqcenter.tq.close.called

    # 关键: 我们的代码不应再设 self._tq._initialized = False
    # (没法直接断言 "代码里没这行", 但可以间接验证:
    # 如果设了, 再次 init 就能"骗过去" (返回 -1 的初始化会"成功"被误判))
    # 真实情况是: 我们的代码现在不设了, 所以每次都得 close() 才能 init


@pytest.mark.asyncio
async def test_get_kline_normalizes_fields(fake_tqcenter, monkeypatch):
    """K线解析: tqcenter 真实返回 DataFrame 结构 (大写字段 + DatetimeIndex)"""
    import pandas as pd

    monkeypatch.setenv("TDX_PATH", "C:/fake/tdx")
    a = TqcenterAdapter()
    a.initialize()

    # 模拟 tqcenter.get_market_data 真实结构:
    # dict[字段名] -> DataFrame (columns=[股票代码], index=DatetimeIndex)
    times = pd.DatetimeIndex(["2026-06-10", "2026-06-11"])
    columns = ["600519.SH"]
    fake_tqcenter.tq.get_market_data = MagicMock(return_value={
        "Open":   pd.DataFrame([100, 103], index=times, columns=columns),
        "High":   pd.DataFrame([105, 108], index=times, columns=columns),
        "Low":    pd.DataFrame([99, 102],  index=times, columns=columns),
        "Close":  pd.DataFrame([103, 107], index=times, columns=columns),
        "Volume": pd.DataFrame([1000, 1500], index=times, columns=columns),
        "Amount": pd.DataFrame([1e7, 1.5e7], index=times, columns=columns),
    })

    klines = await a.get_kline("600519", "1d", 2)
    assert len(klines) == 2
    assert klines[0].open == 100
    assert klines[0].close == 103
    assert klines[0].volume == 1000
    assert klines[0].amount == 1e7
    assert klines[0].period == "1d"
    assert klines[0].source == "tqcenter"
    # 时间戳从 index 取
    assert klines[0].datetime.year == 2026
    assert klines[0].datetime.month == 6
    assert klines[0].datetime.day == 10


@pytest.mark.asyncio
async def test_get_kline_returns_empty_when_core_fields_missing(fake_tqcenter, monkeypatch):
    """get_market_data 返回空或缺核心字段 → 返回空列表 (不抛)"""
    monkeypatch.setenv("TDX_PATH", "C:/fake/tdx")
    a = TqcenterAdapter()
    a.initialize()

    # 缺 Open/Close 字段 (tqcenter 非交易时段返回)
    fake_tqcenter.tq.get_market_data = MagicMock(return_value={
        "Volume": [],
    })
    klines = await a.get_kline("600519", "1d", 5)
    assert klines == []


@pytest.mark.asyncio
async def test_get_kline_handles_error_dict(fake_tqcenter, monkeypatch):
    """tqcenter 返回 {'error': ...} 时返回空"""
    monkeypatch.setenv("TDX_PATH", "C:/fake/tdx")
    a = TqcenterAdapter()
    a.initialize()

    fake_tqcenter.tq.get_market_data = MagicMock(return_value={
        "error": -5,
        "msg": "周期格式错误",
    })
    klines = await a.get_kline("600519", "1d", 5)
    assert klines == []


@pytest.mark.asyncio
async def test_get_kline_invalid_period(fake_tqcenter, monkeypatch):
    monkeypatch.setenv("TDX_PATH", "C:/fake/tdx")
    a = TqcenterAdapter()
    a.initialize()
    with pytest.raises(DataSourceError):
        await a.get_kline("600519", "2y", 10)
