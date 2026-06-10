import os
import pytest

pytestmark = pytest.mark.skipif(
    not os.environ.get("TDX_PATH") or not os.path.exists(os.environ["TDX_PATH"]),
    reason="需要 TDX_PATH 指向真实通达信安装"
)


@pytest.mark.asyncio
async def test_real_get_realtime_quote_600519():
    from stock_mcp.adapters.tqcenter import TqcenterAdapter
    a = TqcenterAdapter()
    a.initialize()
    if not a.enabled:
        pytest.skip("tqcenter 不可用")

    quotes = await a.get_realtime_quote(["600519"])
    assert quotes[0].code == "600519"
    assert quotes[0].price > 0
