"""AKShare 集成测试

akshare 包当前**未装在 venv**。要跑这个集成测试需要:
    uv pip install akshare

如果 akshare 未装, 自动 skip
"""
import os
import sys
from pathlib import Path

import pytest

PROJECT_ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(PROJECT_ROOT / "src"))

akshare_installed = pytest.mark.skipif(
    lambda: True,  # placeholder, see below
    reason="akshare 未装"
)

try:
    import akshare  # noqa
    HAS_AKSHARE = True
except ImportError:
    HAS_AKSHARE = False

pytestmark = pytest.mark.skipif(
    not HAS_AKSHARE,
    reason="akshare 未装, 跳过集成测试. 安装: uv pip install akshare"
)


@pytest.mark.asyncio
async def test_akshare_fundamental_returns_valid_data():
    """真实调 akshare 取茅台基本面"""
    from stock_mcp.adapters.akshare_source import AkshareAdapter
    a = AkshareAdapter()
    if not a.enabled:
        pytest.skip("akshare 适配器未启用")

    fund = await a.get_fundamental("600519")
    if fund is None:
        pytest.skip("akshare 未返回茅台数据 (可能是网络问题)")

    assert fund.code == "600519"
    # 基本面字段合理性 (PE 通常 10-100)
    if fund.pe is not None:
        assert 0 < fund.pe < 200, f"PE {fund.pe} 异常"
    if fund.pb is not None:
        assert 0 < fund.pb < 50, f"PB {fund.pb} 异常"
    if fund.market_cap is not None:
        # 茅台市值通常 1.5-2 万亿 (1.5-2 * 1e12)
        # 但 akshare 字段单位需确认, 这里只做基本范围
        assert fund.market_cap > 0


@pytest.mark.asyncio
async def test_akshare_kline_returns_valid_data():
    """真实调 akshare 取茅台日 K"""
    from stock_mcp.adapters.akshare_source import AkshareAdapter
    a = AkshareAdapter()
    if not a.enabled:
        pytest.skip("akshare 适配器未启用")

    klines = await a.get_kline("600519", "1d", 5)
    if not klines:
        pytest.skip("akshare 未返回 K 线数据")

    assert all(k.code == "600519" for k in klines)
    # OHLC 关系
    for k in klines:
        assert k.low <= k.open <= k.high
        assert k.low <= k.close <= k.high
        assert k.volume > 0
        assert k.source == "akshare"
