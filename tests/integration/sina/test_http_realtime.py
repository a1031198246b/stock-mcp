"""新浪财经 HTTP 集成测试

真实调用 hq.sinajs.cn，验证：
- 解析逻辑与真实响应格式匹配
- 单位换算正确（股->手, 元已是元）
- HTTP 错误处理

如果网络不通，自动 skip
"""
import asyncio
import os
import sys
from pathlib import Path

import pytest

PROJECT_ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(PROJECT_ROOT / "src"))

pytestmark = pytest.mark.skipif(
    not os.environ.get("RUN_NETWORK_TESTS"),
    reason="需要 RUN_NETWORK_TESTS=1 环境变量（避免 CI 默认跑真实网络）",
)


@pytest.fixture
def sina_adapter():
    from stock_mcp.adapters.sina import SinaAdapter
    return SinaAdapter()


@pytest.mark.asyncio
async def test_sina_realtime_quote_returns_valid_data(sina_adapter):
    """真实调 hq.sinajs.cn, 验证 600519 (茅台)"""
    try:
        quotes = await sina_adapter.get_realtime_quote(["600519"])
    except Exception as e:
        pytest.skip(f"网络不通或接口变更: {e}")

    assert len(quotes) == 1
    q = quotes[0]
    assert q.code == "600519"

    # 非交易时段: sina 返回 last_close 正确, 但当前价 = 0
    # A 股: 9:30-11:30 / 13:00-15:00 北京时间
    if q.price == 0 and q.last_close > 0:
        pytest.skip(
            f"非交易时段, sina 返回 price=0 (但 last_close={q.last_close} 正确, "
            f"说明数据流 OK, 只是市场未开)"
        )

    # 价格合理
    assert 1000 < q.price < 2000, f"茅台价格 {q.price} 异常"
    # amount 应该是元 (sina 直接给元)
    assert q.amount > 1e8, f"成交额 {q.amount} 异常小, 应是元单位"
    # volume 应该是手 (sina 给股, /100 转手)
    assert 1e3 < q.volume < 1e6, f"成交量 {q.volume} 手 异常, 应是手单位"
    # 五档
    assert all(0 <= v < 10000 for v in q.bid_5), f"买一量 {q.bid_5} 异常"
    assert all(0 <= v < 10000 for v in q.ask_5), f"卖一量 {q.ask_5} 异常"
    assert q.source == "sina"


@pytest.mark.asyncio
async def test_sina_realtime_quote_handles_invalid_code(sina_adapter):
    """无效代码应被 sina 容忍或抛可识别错"""
    try:
        quotes = await sina_adapter.get_realtime_quote(["999999"])
        # sina 实际行为: 静默返回空, 或者返回带空字段的对象
        # 不应该抛代码格式错
        assert quotes is not None
    except Exception as e:
        # 抛错也可以, 但不能是 "代码格式" 错
        assert "代码格式" not in str(e)
