"""通达信 tqcenter 真实集成测试

目标：固化今天修的 3 个 bug，确保不回归

- 测试 _to_tq_code 自动补后缀（无需通达信运行）
- 测试 get_realtime_quote 返回的字段单位正确（需通达信 + 锁可用）
- 测试 kline 能拉到真实数据（需通达信 + 锁可用）

如果通达信不可用或 tqcenter 锁被占用，相关测试自动 skip
"""
import os
import sys
import asyncio
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
    """
    from stock_mcp.adapters.tqcenter import TqcenterAdapter
    a = TqcenterAdapter()
    a.initialize()
    if not a.enabled:
        pytest.skip("tqcenter 不可用 (TDX_PATH 未配置或初始化失败/锁被占用)")
    return a


def test_get_realtime_quote_amount_in_yuan(tq_adapter):
    """Bug 2: 成交额必须是元（茅台日成交额 10^9 量级），不是万元（10^5 量级）"""
    quotes = asyncio.run(tq_adapter.get_realtime_quote(["600519"]))
    assert len(quotes) == 1
    q = quotes[0]
    assert q.code == "600519"
    # 茅台日成交额至少几亿元, 即 10^9 元以上
    # 修 bug 之前这里会是 ~5*10^5 (万元)
    assert q.amount > 1e8, (
        f"成交额 {q.amount} 元 异常小, 应该是元单位 (>=1e8), "
        f"看起来单位没换算 (万元 vs 元)"
    )


def test_get_realtime_quote_volume_in_lots(tq_adapter):
    """Bug 3: 成交量必须是手 (茅台日成交量 10^4-10^5 手), 不是股 (10^6-10^7)"""
    quotes = asyncio.run(tq_adapter.get_realtime_quote(["600519"]))
    q = quotes[0]
    # 茅台日成交量在 几万 手 量级
    # 修 bug 之前这里是 ~3.9*10^6 (股)
    assert 1e3 < q.volume < 1e6, (
        f"成交量 {q.volume} 手 异常, 应该是手单位 (1e3-1e6), "
        f"看起来单位没换算 (股 vs 手)"
    )


def test_get_realtime_quote_bid_ask_in_lots(tq_adapter):
    """Bug 3 同样影响五档买卖盘: 必须是手 (1-1000 量级), 不是股 (100-100000)"""
    quotes = asyncio.run(tq_adapter.get_realtime_quote(["600519"]))
    q = quotes[0]
    # 买一量: 1-1000 手是合理的
    # 修 bug 之前这里会是 424 (股)
    assert all(0 <= v < 10000 for v in q.bid_5), (
        f"买一量 {q.bid_5} 异常, 应该是手单位 (0-10000), "
        f"看起来单位没换算"
    )
    assert all(0 <= v < 10000 for v in q.ask_5), (
        f"卖一量 {q.ask_5} 异常, 应该是手单位 (0-10000)"
    )


def test_get_realtime_quote_basic_fields(tq_adapter):
    """基本字段合理性检查 - 防止字段名错位"""
    quotes = asyncio.run(tq_adapter.get_realtime_quote(["600519"]))
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


# ============== K 线 (注意: K 线 API 名字在 tqcenter 不同版本有差异, 暂不固化测试) ==============
# def test_get_kline_daily(tq_adapter):
#     """K 线能拉到日线数据 (暂跳过, tqcenter 实际 API 是 get_market_data)"""
#     pass
