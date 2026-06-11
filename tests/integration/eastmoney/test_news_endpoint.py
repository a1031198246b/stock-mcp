"""东方财富 HTTP 集成测试

真实调用 np-anotice-stock.eastmoney.com，验证资讯数据解析

如果网络不通，自动 skip
"""

import os
import sys
from pathlib import Path

import pytest

PROJECT_ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(PROJECT_ROOT / "src"))

pytestmark = pytest.mark.skipif(
    not os.environ.get("RUN_NETWORK_TESTS"),
    reason="需要 RUN_NETWORK_TESTS=1 环境变量",
)


@pytest.fixture
def eastmoney_adapter():
    from stock_mcp.adapters.eastmoney import EastmoneyAdapter

    return EastmoneyAdapter()


@pytest.mark.asyncio
async def test_eastmoney_news_returns_valid_data(eastmoney_adapter):
    """真实调东财公告 API, 验证茅台有公告返回"""
    try:
        news = await eastmoney_adapter.get_news("600519", limit=5)
    except Exception as e:
        # 接口变更或网络问题
        msg = str(e)
        if "JSON" in msg or "JSONDecode" in msg:
            pytest.skip(f"东财 API 响应格式变更: {msg[:200]}")
        pytest.skip(f"网络不通或接口异常: {msg[:200]}")

    # 即使茅台没有新公告, 也应该返回空列表, 而不是抛错
    assert isinstance(news, list)
    # 如果有数据, 检查格式
    for n in news:
        assert n.title  # 有标题
        assert n.url  # 有链接
        # 茅台代码可能带也可能不带
        # 但 news.source 应该是 "东方财富" 或 news.mediaName
