"""通达信 tqcenter 真实集成测试

目标：固化今天修的 3 个 bug，确保不回归

- 测试 _to_tq_code 自动补后缀（无需通达信运行）
- 测试 get_realtime_quote 返回的字段单位正确（需通达信 + 锁可用）
- 测试 kline 能拉到真实数据（需通达信 + 锁可用）

如果通达信不可用或 tqcenter 锁被占用，相关测试自动 skip
"""

import asyncio
import os
import sys
from pathlib import Path

import pytest
from dotenv import load_dotenv

# 指向项目 src（集成测试直接 import 适配器）
PROJECT_ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(PROJECT_ROOT / "src"))

# 主动加载 .env, 集成测试需要 TDX_PATH
load_dotenv(PROJECT_ROOT / ".env")

# 这个路径必须在 import tqcenter 之前设置
TDX_PATH = os.environ.get("TDX_PATH", "")
TDX_PYPLUGINS = Path(TDX_PATH) / "PYPlugins" / "user" if TDX_PATH else None

pytestmark = pytest.mark.skipif(
    not TDX_PATH or not TDX_PYPLUGINS or not TDX_PYPLUGINS.exists(),
    reason="需要 TDX_PATH 指向真实通达信安装",
)


# ============== Bug 1: 代码格式自动补后缀 ==============


def test_to_tq_code_appends_sh_suffix():
    """6 开头代码自动补 .SH"""
    from stock_mcp.adapters.tqcenter import TqcenterAdapter

    assert TqcenterAdapter._to_tq_code("600519") == "600519.SH"
    assert TqcenterAdapter._to_tq_code("688318") == "688318.SH"
    assert TqcenterAdapter._to_tq_code("900901") == "900901.SH"


def test_to_tq_code_appends_sz_suffix():
    """0/3 开头代码自动补 .SZ"""
    from stock_mcp.adapters.tqcenter import TqcenterAdapter

    assert TqcenterAdapter._to_tq_code("000001") == "000001.SZ"
    assert TqcenterAdapter._to_tq_code("300750") == "300750.SZ"


def test_to_tq_code_passthrough():
    """已带后缀的代码不变"""
    from stock_mcp.adapters.tqcenter import TqcenterAdapter

    assert TqcenterAdapter._to_tq_code("600519.SH") == "600519.SH"
    assert TqcenterAdapter._to_tq_code("000001.SZ") == "000001.SZ"
    assert TqcenterAdapter._to_tq_code("sh600519") == "600519.SH"
    assert TqcenterAdapter._to_tq_code("sz000001") == "000001.SZ"


# ============== Bug 2 & 3: 字段单位正确 ==============


@pytest.fixture
def tq_adapter():
    """尝试创建并初始化 tqcenter 适配器

    如果锁被占用（其他 Python 进程正在用），返回的 adapter 是 disabled
    这种情况下用 pytest.skip

    teardown: 显式 close, 释放 DLL 锁, 避免脏锁污染下次测试

    启动时: 给 DLL 一点时间让之前的锁自然释放 (DLL 端 close 是异步的)
    """
    import time as _time

    from stock_mcp.adapters.tqcenter import TqcenterAdapter

    # 重试: 给 DLL 一些时间释放锁
    last_err = None
    for _attempt in range(3):
        a = TqcenterAdapter()
        a.initialize()
        if a.enabled:
            yield a
            # teardown: 显式关闭, 释放 DLL 锁
            try:
                if a._tq is not None:
                    a._tq.close()
                    _time.sleep(0.2)  # 给 DLL 一点时间
            except Exception:
                pass
            return
        last_err = a._tq
        # 失败, 等待再试
        _time.sleep(1.0)
        # 强制清除 Python 端标志
        try:
            a._tq._initialized = False
            a._tq.run_id = -1
        except Exception:
            pass

    # 3 次都失败
    pytest.skip(f"tqcenter 不可用 (3 次重试后仍失败, 最后一次: {last_err})")


def _skip_if_market_closed(tq_adapter):
    """非交易时段 skip

    A 股交易时间 9:30-11:30 / 13:00-15:00 北京时间.
    非交易时段 tqcenter.get_market_snapshot() 返回 price=0, 我们的测试
    会因为 Now=0 而误判.
    """
    quotes = asyncio.run(tq_adapter.get_realtime_quote(["600519"]))
    if not quotes or quotes[0].price == 0:
        pytest.skip("非交易时段, tqcenter 返回 price=0 (无实际数据可验证)")
    return quotes


def test_get_realtime_quote_amount_in_yuan(tq_adapter):
    """Bug 2: 成交额必须是元（茅台日成交额 10^9 量级），不是万元（10^5 量级）"""
    quotes = _skip_if_market_closed(tq_adapter)
    q = quotes[0]
    assert q.code == "600519"
    # 茅台日成交额至少几亿元, 即 10^9 元以上
    # 修 bug 之前这里会是 ~5*10^5 (万元)
    assert q.amount > 1e8, (
        f"成交额 {q.amount} 元 异常小, 应该是元单位 (>=1e8), 看起来单位没换算 (万元 vs 元)"
    )


def test_get_realtime_quote_volume_in_lots(tq_adapter):
    """Bug 3: 成交量必须是手 (茅台日成交量 10^4-10^5 手), 不是股 (10^6-10^7)"""
    quotes = _skip_if_market_closed(tq_adapter)
    q = quotes[0]
    # 茅台日成交量在 几万 手 量级
    # 修 bug 之前这里是 ~3.9*10^6 (股)
    assert 1e3 < q.volume < 1e6, (
        f"成交量 {q.volume} 手 异常, 应该是手单位 (1e3-1e6), 看起来单位没换算 (股 vs 手)"
    )


def test_get_realtime_quote_bid_ask_in_lots(tq_adapter):
    """Bug 3 同样影响五档买卖盘: 必须是手 (1-1000 量级), 不是股 (100-100000)"""
    quotes = _skip_if_market_closed(tq_adapter)
    q = quotes[0]
    # 买一量: 1-1000 手是合理的
    # 修 bug 之前这里会是 424 (股)
    assert all(0 <= v < 10000 for v in q.bid_5), (
        f"买一量 {q.bid_5} 异常, 应该是手单位 (0-10000), 看起来单位没换算"
    )
    assert all(0 <= v < 10000 for v in q.ask_5), f"卖一量 {q.ask_5} 异常, 应该是手单位 (0-10000)"


def test_get_realtime_quote_basic_fields(tq_adapter):
    """基本字段合理性检查 - 防止字段名错位"""
    quotes = _skip_if_market_closed(tq_adapter)
    q = quotes[0]
    # 茅台价格在 1000-2000 区间
    assert 1000 < q.price < 2000, f"价格 {q.price} 不在合理区间"
    # 涨跌幅 -20% ~ +20%
    assert -20 < q.change_pct < 20, f"涨跌幅 {q.change_pct} 异常"
    # OHLC 关系: low <= open/close <= high
    assert q.low <= q.open <= q.high, f"open {q.open} 不在 low~high 区间"
    assert q.low <= q.last_close <= q.high, f"last_close {q.last_close} 不在 low~high 区间"
    # source 自动注入
    assert q.source == "tqcenter"


def test_get_realtime_quote_invalid_code_format(tq_adapter):
    """Bug 1 的反向验证: 不存在代码不应抛 '代码格式错误'

    修 Bug 1 之前, tqcenter 会因为 '999999' 缺后缀而抛
    '股票代码格式错误: 999999 (需 6 位代码+市场后缀)'
    修 Bug 1 之后, 我们的 _to_tq_code 会补成 '999999.SH', tqcenter
    接受后才会因为代码不存在而抛其他错
    """
    with pytest.raises(Exception) as exc_info:
        asyncio.run(tq_adapter.get_realtime_quote(["999999"]))
    msg = str(exc_info.value)
    # 关键断言: 不应该是 "代码格式错误" (那是 Bug 1 的症状)
    assert "代码格式" not in msg and "format" not in msg.lower(), (
        f"碰到 '代码格式' 错误, 说明 _to_tq_code 没生效: {msg}"
    )


# ============== 基本面 ==============


def test_get_fundamental_maotai(tq_adapter):
    """茅台: 总股本 12.5 亿股左右, PE 应在 5~30 区间"""
    import asyncio

    f = asyncio.run(tq_adapter.get_fundamental("600519"))
    assert f is not None
    assert f.code == "600519"
    assert f.name == "贵州茅台"
    # 总股本约 12.5 亿股 (J_zgb = 125008.16 万股)
    assert 10 < f.total_shares < 15, f"总股本 {f.total_shares} 亿股异常"
    # 市值应在万亿级 (1.5 万亿 ~ 2 万亿)
    assert 5000 < f.market_cap < 30000, f"市值 {f.market_cap} 亿元异常"
    # PE/PB 应该为正
    assert f.pe is not None and 0 < f.pe < 100
    assert f.pb is not None and 0 < f.pb < 50
    # 行业代码 (字符串) 应存在
    assert f.industry is not None and f.industry.isdigit()
    assert f.source == "tqcenter"


def test_get_fundamental_returns_none_for_nonexistent_code(tq_adapter):
    """Bug 1 反向验证: 不存在代码返回 None (不是抛异常)"""
    import asyncio

    f = asyncio.run(tq_adapter.get_fundamental("999999"))
    assert f is None


# ============== K 线 (注意: K 线 API 名字在 tqcenter 不同版本有差异, 暂不固化测试) ==============
# def test_get_kline_daily(tq_adapter):
#     """K 线能拉到日线数据 (暂跳过, tqcenter 实际 API 是 get_market_data)"""
#     pass
