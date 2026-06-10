import sys
import pytest
from unittest.mock import MagicMock, AsyncMock
from datetime import datetime
from stock_mcp.adapters.tqcenter import TqcenterAdapter
from stock_mcp.domain.errors import DataSourceError, AuthError


class FakeTqModule:
    """模拟 tqcenter 模块"""

    def __init__(self):
        self.tq = MagicMock()


@pytest.fixture
def fake_tqcenter(monkeypatch):
    fake = FakeTqModule()
    # 让 from-import 拿到这个 fake
    sys.modules["tqcenter"] = fake
    yield fake
    sys.modules.pop("tqcenter", None)


@pytest.mark.asyncio
async def test_initialize_calls_tq_initialize(fake_tqcenter, monkeypatch):
    monkeypatch.setenv("TDX_PATH", "C:/fake/tdx")
    a = TqcenterAdapter()
    a.initialize()  # 同步
    fake_tqcenter.tq.initialize.assert_called_once_with("C:/fake/tdx")


@pytest.mark.asyncio
async def test_initialize_succeeds_sets_enabled(fake_tqcenter, monkeypatch):
    monkeypatch.setenv("TDX_PATH", "C:/fake/tdx")
    a = TqcenterAdapter()
    a.initialize()
    assert a.enabled is True


@pytest.mark.asyncio
async def test_initialize_failure_disables(fake_tqcenter, monkeypatch):
    monkeypatch.setenv("TDX_PATH", "C:/fake/tdx")
    fake_tqcenter.tq.initialize.side_effect = Exception("connection failed")
    a = TqcenterAdapter()
    a.initialize()
    assert a.enabled is False


@pytest.mark.asyncio
async def test_health_check_calls_health_probe(fake_tqcenter, monkeypatch):
    monkeypatch.setenv("TDX_PATH", "C:/fake/tdx")
    a = TqcenterAdapter()
    a.initialize()
    fake_tqcenter.tq.get_stock_list = MagicMock(return_value=["600519.SH"])
    result = await a.health_check()
    assert result is True


@pytest.mark.asyncio
async def test_get_realtime_quote_normalizes_fields(fake_tqcenter, monkeypatch):
    monkeypatch.setenv("TDX_PATH", "C:/fake/tdx")
    a = TqcenterAdapter()
    a.initialize()

    fake_tqcenter.tq.get_market_snapshot = MagicMock(return_value={
        "Now": 1500.0,
        "LastClose": 1463.5,
        "Amount": 1.2e9,
        "Volume": 10000,
        "Open": 1480.0,
        "Max": 1510.0,
        "Min": 1475.0,
        "Buyv": [100, 200, 300, 400, 500],
        "Sellv": [150, 250, 350, 450, 550],
    })
    fake_tqcenter.tq.get_stock_info = MagicMock(return_value={
        "ErrorId": "0", "Name": "贵州茅台", "J_zgb": 0,  # 总股本（万）— 0
    })

    quotes = await a.get_realtime_quote(["600519"])
    assert len(quotes) == 1
    q = quotes[0]
    assert q.code == "600519"
    assert q.price == 1500.0
    assert q.change_pct == pytest.approx(2.49, rel=0.01)
    assert q.bid_5 == [100, 200, 300, 400, 500]
    assert q.ask_5 == [150, 250, 350, 450, 550]
    assert q.source == "tqcenter"


@pytest.mark.asyncio
async def test_health_check_failure_returns_false(fake_tqcenter, monkeypatch):
    monkeypatch.setenv("TDX_PATH", "C:/fake/tdx")
    a = TqcenterAdapter()
    a.initialize()
    fake_tqcenter.tq.get_stock_list = MagicMock(side_effect=Exception("timeout"))
    result = await a.health_check()
    assert result is False
