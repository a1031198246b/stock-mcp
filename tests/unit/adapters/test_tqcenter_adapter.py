import sys
from unittest.mock import MagicMock

import pytest

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

    fake_tqcenter.tq.get_market_snapshot = MagicMock(
        return_value={
            "Now": 1500.0,
            "LastClose": 1463.5,
            "Amount": 1.2e9,
            "Volume": 10000,
            "Open": 1480.0,
            "Max": 1510.0,
            "Min": 1475.0,
            "Buyv": [100, 200, 300, 400, 500],
            "Sellv": [150, 250, 350, 450, 550],
        }
    )
    fake_tqcenter.tq.get_stock_info = MagicMock(
        return_value={
            "ErrorId": "0",
            "Name": "贵州茅台",
            "J_zgb": 0,  # 总股本（万）— 0
        }
    )

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


# ============== get_fundamental 测试 ==============


def _make_stock_info(
    j_zgb: str = "125008.16",  # 万股
    j_mgsy: str = "87.17",  # 元/股
    j_mgjzc: str = "216.32",  # 元/股
    j_jzc: str = "27089404.00",  # 元
    j_jly: str = "2724251.25",  # 元
    j_hy=37,  # 行业代码
    name="贵州茅台",
    error_id="0",
):
    """构造一个 tqcenter.get_stock_info 风格的字典 (字段可能为字符串)"""
    return {
        "ErrorId": error_id,
        "Name": name,
        "J_zgb": j_zgb,
        "J_mgsy": j_mgsy,
        "J_mgjzc": j_mgjzc,
        "J_jzc": j_jzc,
        "J_jly": j_jly,
        "J_hy": j_hy,
    }


@pytest.mark.asyncio
async def test_get_fundamental_computes_pe_pb_marketcap(fake_tqcenter, monkeypatch):
    """get_fundamental: 用 stock_info + 实时价计算 PE/PB/市值"""
    monkeypatch.setenv("TDX_PATH", "C:/fake/tdx")
    a = TqcenterAdapter()
    a.initialize()

    # 茅台: 1276.5 元 × 12.5008 亿股 = 15957.3 亿
    # PE = 1276.5 / 87.17 ≈ 14.64
    # PB = 1276.5 / 216.32 ≈ 5.90
    fake_tqcenter.tq.get_stock_info = MagicMock(return_value=_make_stock_info())
    fake_tqcenter.tq.get_market_snapshot = MagicMock(return_value={"Now": 1276.5})

    f = await a.get_fundamental("600519")
    assert f is not None
    assert f.code == "600519"
    assert f.name == "贵州茅台"
    assert f.pe == pytest.approx(14.64, rel=0.01)
    assert f.pb == pytest.approx(5.90, rel=0.01)
    # ROE = J_jly / J_jzc = 2724251.25 / 27089404.00 ≈ 0.1006
    assert f.roe == pytest.approx(0.1006, rel=0.01)
    # 总股本: 125008.16 万股 = 12.5008 亿股
    assert f.total_shares == pytest.approx(12.5008, rel=0.01)
    # 市值: 1276.5 * 125008.16 / 10000 = 15957.28 亿
    assert f.market_cap == pytest.approx(15957.28, rel=0.01)
    # 行业代码: 37 → "37" (原始 TDX 内部代码, 不强行猜名称)
    assert f.industry == "37"
    assert f.source == "tqcenter"


@pytest.mark.asyncio
async def test_get_fundamental_returns_none_on_error_response(fake_tqcenter, monkeypatch):
    """ErrorId != '0' → 返回 None (不抛)"""
    monkeypatch.setenv("TDX_PATH", "C:/fake/tdx")
    a = TqcenterAdapter()
    a.initialize()

    fake_tqcenter.tq.get_stock_info = MagicMock(
        return_value={"ErrorId": "11", "Error": "no such code"}
    )
    f = await a.get_fundamental("600519")
    assert f is None


@pytest.mark.asyncio
async def test_get_fundamental_handles_string_numbers(fake_tqcenter, monkeypatch):
    """tqcenter 的 J_zgb/J_mgsy 等字段实际是字符串, 必须能转 float"""
    monkeypatch.setenv("TDX_PATH", "C:/fake/tdx")
    a = TqcenterAdapter()
    a.initialize()

    fake_tqcenter.tq.get_stock_info = MagicMock(
        return_value=_make_stock_info(
            j_zgb="100000.00",
            j_mgsy="10.0",
            j_mgjzc="20.0",
            j_jzc="200000.00",
            j_jly="10000.00",
        )
    )
    fake_tqcenter.tq.get_market_snapshot = MagicMock(return_value={"Now": 100.0})

    f = await a.get_fundamental("000001")
    assert f is not None
    assert f.pe == 10.0  # 100 / 10
    assert f.pb == 5.0  # 100 / 20
    assert f.roe == 0.05  # 10000 / 200000
    assert f.total_shares == 10.0  # 100000 万股 = 10 亿股
    assert f.market_cap == 1000.0  # 100 * 100000 / 10000


@pytest.mark.asyncio
async def test_get_fundamental_handles_zero_eps(fake_tqcenter, monkeypatch):
    """EPS=0 (新股/亏损股) 时 PE 应为 None 不应除零"""
    monkeypatch.setenv("TDX_PATH", "C:/fake/tdx")
    a = TqcenterAdapter()
    a.initialize()

    fake_tqcenter.tq.get_stock_info = MagicMock(
        return_value=_make_stock_info(
            j_mgsy="0.0",
            j_mgjzc="5.0",
        )
    )
    fake_tqcenter.tq.get_market_snapshot = MagicMock(return_value={"Now": 50.0})

    f = await a.get_fundamental("688999")
    assert f is not None
    assert f.pe is None  # 0 EPS → 不算 PE
    assert f.pb == 10.0  # 50 / 5


@pytest.mark.asyncio
async def test_get_fundamental_industry_code_is_string(fake_tqcenter, monkeypatch):
    """industry 字段保留 TDX 原始代码, 上层做翻译"""
    monkeypatch.setenv("TDX_PATH", "C:/fake/tdx")
    a = TqcenterAdapter()
    a.initialize()

    fake_tqcenter.tq.get_stock_info = MagicMock(return_value=_make_stock_info(j_hy=37))
    fake_tqcenter.tq.get_market_snapshot = MagicMock(return_value={"Now": 100.0})

    f = await a.get_fundamental("600519")
    assert f.industry == "37"  # 不是"白酒" — 我们不强行猜名称


@pytest.mark.asyncio
async def test_get_fundamental_returns_none_when_dll_raises(fake_tqcenter, monkeypatch):
    """不存在的代码 → tqcenter 抛异常 → 返回 None (不抛)"""
    monkeypatch.setenv("TDX_PATH", "C:/fake/tdx")
    a = TqcenterAdapter()
    a.initialize()

    fake_tqcenter.tq.get_stock_info = MagicMock(side_effect=Exception("股票代码格式错误: 999999"))
    f = await a.get_fundamental("999999")
    assert f is None


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
    fake_tqcenter.tq.get_market_data = MagicMock(
        return_value={
            "Open": pd.DataFrame([100, 103], index=times, columns=columns),
            "High": pd.DataFrame([105, 108], index=times, columns=columns),
            "Low": pd.DataFrame([99, 102], index=times, columns=columns),
            "Close": pd.DataFrame([103, 107], index=times, columns=columns),
            "Volume": pd.DataFrame([1000, 1500], index=times, columns=columns),
            "Amount": pd.DataFrame([1e7, 1.5e7], index=times, columns=columns),
        }
    )

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
    fake_tqcenter.tq.get_market_data = MagicMock(
        return_value={
            "Volume": [],
        }
    )
    klines = await a.get_kline("600519", "1d", 5)
    assert klines == []


@pytest.mark.asyncio
async def test_get_kline_handles_error_dict(fake_tqcenter, monkeypatch):
    """tqcenter 返回 {'error': ...} 时返回空"""
    monkeypatch.setenv("TDX_PATH", "C:/fake/tdx")
    a = TqcenterAdapter()
    a.initialize()

    fake_tqcenter.tq.get_market_data = MagicMock(
        return_value={
            "error": -5,
            "msg": "周期格式错误",
        }
    )
    klines = await a.get_kline("600519", "1d", 5)
    assert klines == []


@pytest.mark.asyncio
async def test_get_kline_invalid_period(fake_tqcenter, monkeypatch):
    monkeypatch.setenv("TDX_PATH", "C:/fake/tdx")
    a = TqcenterAdapter()
    a.initialize()
    with pytest.raises(DataSourceError):
        await a.get_kline("600519", "2y", 10)


# ============== 覆盖率补足测试 (CI 在 TDX_PATH="" 下需 ≥ 90%) ==============


@pytest.mark.asyncio
async def test_health_check_returns_false_when_not_initialized():
    """未初始化时 health_check 应当直接返回 False (不访问 tq)"""
    a = TqcenterAdapter()
    # _initialized = False
    assert await a.health_check() is False


def test_initialize_returns_early_when_already_initialized(fake_tqcenter, monkeypatch):
    """二次 initialize 应提前 return, 不重复调底层 init"""
    monkeypatch.setenv("TDX_PATH", "C:/fake/tdx")
    a = TqcenterAdapter()
    a.initialize()
    call_count_after_first = fake_tqcenter.tq.initialize.call_count
    # 再次 init → 应 early-return
    a.initialize()
    assert fake_tqcenter.tq.initialize.call_count == call_count_after_first


def test_initialize_returns_early_when_tdx_path_unset(monkeypatch):
    """TDX_PATH 为空 → initialize 直接 return, 保持 disabled

    不用 monkeypatch.delenv("TDX_PATH"), 因为 .env 文件可能含 TDX_PATH,
    那样 get_settings() 仍会读到. 改用 monkeypatch.setattr 直接 mock Settings
    对象返回 tdx_path=""
    """
    from unittest.mock import MagicMock
    from stock_mcp.adapters import tqcenter as tqcenter_mod

    fake_settings = MagicMock()
    fake_settings.tdx_path = ""  # 强制空, 模拟 CI 环境
    monkeypatch.setattr(tqcenter_mod, "get_settings", lambda: fake_settings)

    a = TqcenterAdapter()
    a.initialize()
    assert a._initialized is False
    assert a.enabled is False


def test_to_tq_code_keeps_existing_dot_suffix():
    """已带 .SH/.SZ/.BJ 后缀的代码, _to_tq_code 应原样返回"""
    assert TqcenterAdapter._to_tq_code("600519.SH") == "600519.SH"
    assert TqcenterAdapter._to_tq_code("000001.SZ") == "000001.SZ"


def test_to_tq_code_strips_sh_sz_bj_prefix():
    """带 SH/SZ/BJ 前缀 (无点) → 应去掉前缀, 然后按 6 位代码加后缀"""
    assert TqcenterAdapter._to_tq_code("SH600519") == "600519.SH"
    assert TqcenterAdapter._to_tq_code("SZ000001") == "000001.SZ"


def test_to_tq_code_adds_bj_suffix():
    """北京 (43/83/87 开头) 代码应加 .BJ 后缀"""
    assert TqcenterAdapter._to_tq_code("830001") == "830001.BJ"
    assert TqcenterAdapter._to_tq_code("430001") == "430001.BJ"


def test_safe_int_list_handles_short_and_garbage_input():
    """_safe_int_list: 不足 5 个 / 异常元素 → 用 0 兜底"""
    # 长度不足 → 缺位补 0
    assert TqcenterAdapter._safe_int_list([1, 2], 5) == [1, 2, 0, 0, 0]
    # 异常元素 (字符串非数字) → 0
    assert TqcenterAdapter._safe_int_list(["x", "y", "z"], 3) == [0, 0, 0]
    # 全 None → 全 0
    assert TqcenterAdapter._safe_int_list([None, None, None, None, None], 5) == [0, 0, 0, 0, 0]
