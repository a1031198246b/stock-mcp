import sys
from unittest.mock import MagicMock

import pandas as pd
import pytest

from stock_mcp.adapters.iwencai import IwencaiAdapter
from stock_mcp.domain.errors import AuthError, DataSourceError


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
async def test_initialize_enabled_without_cookie(fake_pywencai, monkeypatch):
    """没有 cookie 时, 只要 pywencai 已装就应该启用 (匿名模式)."""
    monkeypatch.delenv("IWENCAI_COOKIE", raising=False)
    a = IwencaiAdapter()
    a.initialize()
    assert a.enabled is True


@pytest.mark.asyncio
async def test_initialize_disabled_when_pywencai_not_installed(monkeypatch):
    """pywencai 没装时, 不管有没有 cookie 都应该禁用."""
    sys.modules.pop("pywencai", None)
    sys.modules["pywencai"] = None  # 让 import 抛 ImportError
    try:
        monkeypatch.delenv("IWENCAI_COOKIE", raising=False)
        a = IwencaiAdapter()
        a.initialize()
        assert a.enabled is False
    finally:
        sys.modules.pop("pywencai", None)


@pytest.mark.asyncio
async def test_query_stocks_passes_none_cookie_when_unconfigured(
    fake_pywencai, monkeypatch
):
    """未配置 cookie 时, 应该把 cookie=None 透传给 pywencai."""
    monkeypatch.delenv("IWENCAI_COOKIE", raising=False)
    fake_pywencai.get.return_value = pd.DataFrame(
        {"股票代码": ["600519"], "股票名称": ["贵州茅台"]}
    )
    a = IwencaiAdapter()
    a.initialize()

    await a.query_stocks("市值<100亿")

    fake_pywencai.get.assert_called_once()
    call_kwargs = fake_pywencai.get.call_args.kwargs
    assert call_kwargs["cookie"] is None
    assert call_kwargs["question"] == "市值<100亿"


@pytest.mark.asyncio
async def test_query_stocks_works_without_cookie(fake_pywencai, monkeypatch):
    """匿名模式能拿到结果 (pywencai 返回 DataFrame), 解析逻辑应正常工作."""
    monkeypatch.delenv("IWENCAI_COOKIE", raising=False)
    fake_pywencai.get.return_value = pd.DataFrame(
        {
            "股票代码": ["600519", "000001"],
            "股票名称": ["贵州茅台", "平安银行"],
            "ROE": [0.30, 0.12],
        }
    )
    a = IwencaiAdapter()
    a.initialize()

    result = await a.query_stocks("ROE > 0.1")
    assert len(result) == 2
    assert result[0].code == "600519"
    assert result[0].name == "贵州茅台"
    assert result[0].matched_fields["ROE"] == 0.30
    assert result[1].code == "000001"


@pytest.mark.asyncio
async def test_query_stocks_no_cookie_raises_data_source_error_not_auth_error(
    fake_pywencai, monkeypatch
):
    """匿名模式下即使 pywencai 抛出含 'cookie'/'登录' 字样的错误,
    也不应归类为 AuthError, 因为根本没配置 cookie."""
    monkeypatch.delenv("IWENCAI_COOKIE", raising=False)
    fake_pywencai.get.side_effect = Exception("未登录或登录已过期")
    a = IwencaiAdapter()
    a.initialize()

    with pytest.raises(DataSourceError):
        await a.query_stocks("条件")


@pytest.mark.asyncio
async def test_iwencai_query_stocks(fake_pywencai, monkeypatch):
    monkeypatch.setenv("IWENCAI_COOKIE", "v=123")
    fake_pywencai.get.return_value = pd.DataFrame(
        {
            "股票代码": ["600519", "000001"],
            "股票名称": ["贵州茅台", "平安银行"],
            "ROE": [0.30, 0.12],
        }
    )
    a = IwencaiAdapter()
    a.initialize()

    result = await a.query_stocks("ROE > 0.1")
    assert len(result) == 2
    assert result[0].code == "600519"
    assert result[0].matched_fields["ROE"] == 0.30
    # 显式传了 cookie 时应该把 cookie 原样透传
    assert fake_pywencai.get.call_args.kwargs["cookie"] == "v=123"


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
