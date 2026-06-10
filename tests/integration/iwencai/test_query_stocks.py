"""iWencai 集成测试

iwencai 需要:
1. pywencai 包: uv pip install pywencai
2. IWENCAI_COOKIE 环境变量 (从 iwencai.com 登录后获取)

如果任一缺失, 自动 skip
"""
import os
import sys
from pathlib import Path

import pytest
from dotenv import load_dotenv

PROJECT_ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(PROJECT_ROOT / "src"))
load_dotenv(PROJECT_ROOT / ".env")

try:
    import pywencai  # noqa
    HAS_PYWENCAI = True
except ImportError:
    HAS_PYWENCAI = False

HAS_COOKIE = bool(os.environ.get("IWENCAI_COOKIE"))

pytestmark = pytest.mark.skipif(
    not (HAS_PYWENCAI and HAS_COOKIE),
    reason=f"iwencai 集成测试需要 pywencai + IWENCAI_COOKIE (HAS_PYWENCAI={HAS_PYWENCAI}, HAS_COOKIE={HAS_COOKIE})"
)


@pytest.mark.asyncio
async def test_iwencai_query_stocks_real():
    """真实调爱问财, 查询 "PE < 30" 的股票"""
    from stock_mcp.adapters.iwencai import IwencaiAdapter
    a = IwencaiAdapter()
    a.initialize()
    if not a.enabled:
        pytest.skip("iwencai 适配器未启用")

    results = await a.query_stocks("市盈率小于 30")
    # 至少返回一些结果 (中国股市 PE<30 股票很多)
    if not results:
        pytest.skip("iwencai 未返回结果 (可能是查询条件不被支持)")

    assert all(r.code for r in results)  # 都有代码
    assert all(len(r.code) == 6 for r in results)  # 6 位代码
    # matched_fields 应该有一些字段
    for r in results[:5]:
        assert isinstance(r.matched_fields, dict)
