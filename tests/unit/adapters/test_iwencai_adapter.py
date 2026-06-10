import sys
import pytest
from unittest.mock import MagicMock
from stock_mcp.adapters.iwencai import IwencaiAdapter
from stock_mcp.domain.errors import AuthError


class FakePywencaiModule:
    def __init__(self):
        self.get = MagicMock()


@pytest.fixture
def fake_pywencai(monkeypatch):
    fake = FakePywencaiModule()
    sys.modules["pywencai"] = fake
    yield fake
    sys.modules.pop("pywencai", None)


@pytest.mark.asyncio
async def test_iwencai_disabled_without_cookie(fake_pywencai, monkeypatch):
    monkeypatch.delenv("IWENCAI_COOKIE", raising=False)
    a = IwencaiAdapter()
    a.initialize()
    assert a.enabled is False


@pytest.mark.asyncio
async def test_iwencai_query_stocks(fake_pywencai, monkeypatch):
    monkeypatch.setenv("IWENCAI_COOKIE", "v=123")
    import pandas as pd
    fake_pywencai.get.return_value = pd.DataFrame({
        "股票代码": ["600519", "000001"],
        "股票名称": ["贵州茅台", "平安银行"],
        "ROE": [0.30, 0.12],
    })
    a = IwencaiAdapter()
    a.initialize()

    result = await a.query_stocks("ROE > 0.1")
    assert len(result) == 2
    assert result[0].code == "600519"
    assert result[0].matched_fields["ROE"] == 0.30


@pytest.mark.asyncio
async def test_iwencai_handles_cookie_expired(fake_pywencai, monkeypatch):
    monkeypatch.setenv("IWENCAI_COOKIE", "v=expired")
    fake_pywencai.get.side_effect = Exception("未登录或登录已过期")
    a = IwencaiAdapter()
    a.initialize()

    with pytest.raises(AuthError):
        await a.query_stocks("条件")


@pytest.mark.asyncio
async def test_iwencai_default_methods_not_supported(fake_pywencai, monkeypatch):
    """默认的 4 个核心方法都抛 NotImplementedError"""
    monkeypatch.setenv("IWENCAI_COOKIE", "v=123")
    a = IwencaiAdapter()
    a.initialize()

    with pytest.raises(NotImplementedError):
        await a.get_realtime_quote(["600519"])
