"""验证现有 5 个适配器 supported_markets 默认值"""

from stock_mcp.adapters.akshare_source import AkshareAdapter
from stock_mcp.adapters.eastmoney import EastmoneyAdapter
from stock_mcp.adapters.iwencai import IwencaiAdapter
from stock_mcp.adapters.sina import SinaAdapter
from stock_mcp.adapters.tqcenter import TqcenterAdapter


def test_default_supported_markets_is_a_stock():
    for cls in [TqcenterAdapter, SinaAdapter, AkshareAdapter, EastmoneyAdapter, IwencaiAdapter]:
        assert cls.supported_markets == ["a_stock"], f"{cls.__name__} should default to a_stock"
