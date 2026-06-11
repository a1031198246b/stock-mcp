"""server.py 集成测试 — 验证 create_server 装配各服务和工具

使用 mock 替换所有外部适配器, 避免依赖 TDX_PATH / iwencai cookie / 网络。
"""

from unittest.mock import MagicMock, patch

import pytest
from fastmcp import FastMCP


@pytest.fixture
def mock_adapters(monkeypatch, temp_cache_dir, mock_env):
    """Mock 5 个适配器 + 缓存, 装配 create_server 所需的全部依赖

    返回 (mcp, services) 元组, 供测试验证装配结果。
    """

    # Mock 所有适配器类, 让它们的 __init__ 和 initialize 不做真实工作
    def _make_mock_adapter_class(name: str):
        cls = MagicMock()
        cls.name = name
        # 返回的实例: enabled=False 防止任何副作用
        instance = MagicMock()
        instance.name = name
        instance.priority = 1
        instance.enabled = False
        instance.initialize = MagicMock()
        cls.return_value = instance
        return cls

    tq_mock = _make_mock_adapter_class("tqcenter")
    sina_mock = _make_mock_adapter_class("sina")
    akshare_mock = _make_mock_adapter_class("akshare")
    eastmoney_mock = _make_mock_adapter_class("eastmoney")
    iwencai_mock = _make_mock_adapter_class("iwencai")
    bao_mock = _make_mock_adapter_class("baostock")
    yf_mock = _make_mock_adapter_class("yfinance")

    monkeypatch.setattr("stock_mcp.server.TqcenterAdapter", tq_mock)
    monkeypatch.setattr("stock_mcp.server.SinaAdapter", sina_mock)
    monkeypatch.setattr("stock_mcp.server.AkshareAdapter", akshare_mock)
    monkeypatch.setattr("stock_mcp.server.EastmoneyAdapter", eastmoney_mock)
    monkeypatch.setattr("stock_mcp.server.IwencaiAdapter", iwencai_mock)
    monkeypatch.setattr("stock_mcp.server.BaostockAdapter", bao_mock)
    monkeypatch.setattr("stock_mcp.server.YfinanceAdapter", yf_mock)

    # 设置缓存目录到临时目录, 避免污染工作区
    monkeypatch.setenv("CACHE_DIR", str(temp_cache_dir))
    monkeypatch.setenv("LOG_LEVEL", "WARNING")

    return {
        "tq": tq_mock,
        "sina": sina_mock,
        "akshare": akshare_mock,
        "eastmoney": eastmoney_mock,
        "iwencai": iwencai_mock,
        "baostock": bao_mock,
        "yfinance": yf_mock,
    }


def test_create_server_returns_fastmcp_instance(mock_adapters):
    """create_server() 应返回 FastMCP 实例"""
    from stock_mcp.server import create_server

    mcp = create_server()
    assert isinstance(mcp, FastMCP)


def test_create_server_initializes_all_adapters(mock_adapters):
    """create_server() 应调用所有适配器的 initialize()"""
    from stock_mcp.server import create_server

    create_server()

    mock_adapters["tq"].return_value.initialize.assert_called_once()
    mock_adapters["iwencai"].return_value.initialize.assert_called_once()


def test_create_server_registers_ping_tool(mock_adapters):
    """create_server() 至少注册 ping 工具"""
    from stock_mcp.server import create_server

    mcp = create_server()
    # 使用 list_tools 验证（同步方式需在事件循环中）
    import asyncio

    tools = asyncio.run(mcp.list_tools())
    names = {t.name for t in tools}
    assert "ping" in names


def test_create_server_registers_baostock_and_yfinance(mock_adapters):
    """server 应该装配 baostock + yfinance 适配器"""
    from stock_mcp.server import create_server
    from fastmcp import FastMCP
    mcp = create_server()
    assert isinstance(mcp, FastMCP)
    # 验证 baostock / yfinance 适配器已注册 (通过 list_tools 看)
    import asyncio
    tools = asyncio.run(mcp.list_tools())
    tool_names = {t.name for t in tools}
    # financial_statement 应该被注册
    # (具体 tool name 由 Task 8 step 4 决定)
    assert "get_financial_statement" in tool_names, (
        f"get_financial_statement not registered. Tools: {tool_names}"
    )


def test_create_server_registers_all_data_tools(mock_adapters):
    """create_server() 应注册所有数据类工具"""
    import asyncio

    from stock_mcp.server import create_server

    mcp = create_server()
    tools = asyncio.run(mcp.list_tools())
    names = {t.name for t in tools}

    expected = {
        "ping",
        "get_realtime_quote",
        "get_kline",
        "get_fundamental",
        "get_news",
        "query_stocks",
    }
    # 全部工具应被注册（server.py 装配了 5 个 service）
    assert expected.issubset(names), f"Missing: {expected - names}"


def test_create_server_passes_all_adapters_to_registry(mock_adapters):
    """AdapterRegistry 应收到 7 个适配器实例 (含 baostock + yfinance)"""
    from stock_mcp.server import create_server

    # 通过 patch AdapterRegistry 抓取构造参数
    captured = {}

    class FakeRegistry:
        def __init__(self, adapters):
            captured["adapters"] = adapters

    import stock_mcp.server as server_module

    with patch.object(server_module, "AdapterRegistry", FakeRegistry):
        create_server()

    assert "adapters" in captured
    assert len(captured["adapters"]) == 7


def test_main_runs_server_with_stdio_transport(mock_adapters):
    """main() 应调用 mcp.run(transport="stdio") 启动 stdio 服务"""
    import stock_mcp.server as server_module

    # 抓取 create_server 返回的 mcp 实例上的 run 调用
    captured: dict = {}

    class _FakeMCP:
        def run(self, transport: str) -> None:
            captured["transport"] = transport

    with patch.object(server_module, "create_server", return_value=_FakeMCP()):
        server_module.main()

    assert captured["transport"] == "stdio"
