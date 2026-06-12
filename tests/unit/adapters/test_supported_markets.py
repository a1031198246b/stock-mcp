"""验证现有 7 个适配器 supported_markets 默认值"""

from stock_mcp.adapters.akshare_source import AkshareAdapter
from stock_mcp.adapters.eastmoney import EastmoneyAdapter
from stock_mcp.adapters.iwencai import IwencaiAdapter
from stock_mcp.adapters.sina import SinaAdapter
from stock_mcp.adapters.tencent import TencentAdapter
from stock_mcp.adapters.tqcenter import TqcenterAdapter


def test_default_supported_markets():
    """每个适配器必须包含 'a_stock' (基础), 但可以多市场支持"""
    expected = {
        TqcenterAdapter: ["a_stock"],
        SinaAdapter: ["a_stock", "hk", "us"],  # 港美股实时 2026-06-12
        AkshareAdapter: ["a_stock"],
        EastmoneyAdapter: ["a_stock", "hk", "us"],  # 港美股 2026-06-12
        IwencaiAdapter: ["a_stock"],
        TencentAdapter: ["a_stock", "hk", "us"],  # 港美股 K线 2026-06-12
    }
    for cls, markets in expected.items():
        assert cls.supported_markets == markets, (
            f"{cls.__name__}: {cls.supported_markets} != {markets}"
        )
