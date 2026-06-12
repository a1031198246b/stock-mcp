"""EastmoneyAdapter 单测 (respx mock)"""

import httpx
import pytest
import respx


# ==== 资讯 (A 股) ====
@pytest.mark.asyncio
async def test_get_news_eastmoney():
    """模拟东财公告 API (np-anotice-stock 端点)"""
    sample = {
        "data": {
            "list": [
                {
                    "art_code": "AN202606021823168597",
                    "title": "贵州茅台2025年度股东会会议资料",
                    "notice_date": "2026-06-03 00:00:00",
                    "display_time": "2026-06-02 20:07:18",
                    "columns": [{"column_name": "股东大会资料"}],
                    "codes": [{"short_name": "贵州茅台"}],
                },
            ]
        }
    }
    with respx.mock() as router:
        router.get(url__regex=r".*np-anotice-stock\.eastmoney\.com.*").respond(200, json=sample)
        from stock_mcp.adapters.eastmoney import EastmoneyAdapter

        a = EastmoneyAdapter()
        news = await a.get_news("600519", limit=10)
        assert len(news) == 1
        assert news[0].title == "贵州茅台2025年度股东会会议资料"
        assert news[0].source == "股东大会资料"


# ==== 港美股 实时 (单股 secid) ====
@pytest.mark.asyncio
async def test_supported_markets_includes_hk_us():
    """supported_markets 必须含 a_stock/hk/us"""
    from stock_mcp.adapters.eastmoney import EastmoneyAdapter

    a = EastmoneyAdapter()
    assert "a_stock" in a.supported_markets
    assert "hk" in a.supported_markets
    assert "us" in a.supported_markets


@pytest.mark.asyncio
async def test_get_realtime_quote_hk():
    """港股实时 - 单股 secid 查询 (3 位小数, ÷1000)"""
    from stock_mcp.adapters.eastmoney import EastmoneyAdapter

    sample = {
        "data": {
            "f43": 462000,  # high ×1000
            "f44": 469800,  # open
            "f45": 459400,  # low
            "f46": 465600,  # last_close
            "f47": 6298007,  # volume
            "f48": 2866186288.0,  # amount
            "f60": 457200,  # now ×1000
            "f169": -8400,
            "f170": -180,  # -1.80%
            "f171": 149,
        }
    }
    with respx.mock() as router:
        router.get(url__regex=r".*push2\.eastmoney\.com.*stock/get.*").respond(200, json=sample)
        a = EastmoneyAdapter()
        quotes = await a.get_realtime_quote(["00700"], market="hk")
        assert len(quotes) == 1
        q = quotes[0]
        assert q.code == "00700"
        assert q.price == 457.2
        assert q.change_pct == -1.80
        assert q.high == 462.0
        assert q.low == 459.4
        assert q.last_close == 465.6
        assert q.market == "hk"
        assert q.source == "eastmoney"


@pytest.mark.asyncio
async def test_get_realtime_quote_us():
    """美股实时 - 单股 secid 查询 (2 位小数, ÷100)"""
    from stock_mcp.adapters.eastmoney import EastmoneyAdapter

    sample = {
        "data": {
            "f43": 29563,
            "f44": 29372,
            "f45": 28959,
            "f46": 29158,
            "f47": 42572497,
            "f48": 12521172736.0,
            "f60": 29563,
            "f169": 405,
            "f170": 139,
            "f171": 254,
        }
    }
    with respx.mock() as router:
        router.get(url__regex=r".*push2\.eastmoney\.com.*stock/get.*").respond(200, json=sample)
        a = EastmoneyAdapter()
        quotes = await a.get_realtime_quote(["AAPL"], market="us")
        assert len(quotes) == 1
        q = quotes[0]
        assert q.code == "AAPL"
        assert q.price == 295.63
        assert q.change_pct == 1.39
        assert q.high == 295.63
        assert q.low == 289.59
        assert q.market == "us"


@pytest.mark.asyncio
async def test_get_realtime_quote_multiple_stocks_concurrent():
    """多只股票: 验证 secid 并发查询, 各自返回正确"""
    from stock_mcp.adapters.eastmoney import EastmoneyAdapter

    samples = {
        "116.00700": {
            "data": {
                "f60": 457200,
                "f170": -180,
                "f43": 462000,
                "f44": 469800,
                "f45": 459400,
                "f46": 465600,
                "f47": 6298007,
                "f48": 2.8e9,
            }
        },
        "116.09988": {
            "data": {
                "f60": 95750,
                "f170": 117,
                "f43": 96000,
                "f44": 94000,
                "f45": 93500,
                "f46": 94000,
                "f47": 100,
                "f48": 1e6,
            }
        },
    }

    def _side_effect(request):
        url = str(request.url)
        for secid, sample in samples.items():
            if secid in url:
                return httpx.Response(200, json=sample)
        return httpx.Response(404)

    with respx.mock() as router:
        router.get(url__regex=r".*push2\.eastmoney\.com.*stock/get.*").mock(
            side_effect=_side_effect
        )
        a = EastmoneyAdapter()
        quotes = await a.get_realtime_quote(["00700", "09988"], market="hk")
        assert len(quotes) == 2
        codes = {q.code for q in quotes}
        assert codes == {"00700", "09988"}


@pytest.mark.asyncio
async def test_get_realtime_quote_handles_no_data():
    """secid 返回空 data (停牌/不存在) → 该股跳过, 不 crash"""
    from stock_mcp.adapters.eastmoney import EastmoneyAdapter

    sample = {"data": {}}
    with respx.mock() as router:
        router.get(url__regex=r".*push2\.eastmoney\.com.*stock/get.*").respond(200, json=sample)
        a = EastmoneyAdapter()
        quotes = await a.get_realtime_quote(["00700"], market="hk")
        assert quotes == []


@pytest.mark.asyncio
async def test_get_realtime_quote_a_stock_returns_empty():
    """a_stock 走别的源, adapter 返回空"""
    from stock_mcp.adapters.eastmoney import EastmoneyAdapter

    a = EastmoneyAdapter()
    quotes = await a.get_realtime_quote(["600519"], market="a_stock")
    assert quotes == []


# ==== K线 ====
@pytest.mark.asyncio
async def test_get_kline_hk():
    """港股 K线 - 验证 kline 字符串解析"""
    from stock_mcp.adapters.eastmoney import EastmoneyAdapter

    sample = {
        "data": {
            "code": "00700",
            "market": 116,
            "name": "腾讯控股",
            "decimal": 3,
            "klines": [
                "2026-06-09,443.800,453.200,468.400,443.200,37387399,17187726592.000,5.65,1.52,6.800,0.41",
                "2026-06-10,454.800,465.600,471.000,451.600,35788237,16620278768.000,4.28,2.74,12.400,0.39",
                "2026-06-11,469.800,457.200,475.600,455.000,28580619,13202489600.000,4.42,-1.80,-8.400,0.31",
            ],
        }
    }
    with respx.mock() as router:
        router.get(url__regex=r".*push2his\.eastmoney\.com.*kline.*").respond(200, json=sample)
        a = EastmoneyAdapter()
        klines = await a.get_kline("00700", "1d", 5, market="hk")
        assert len(klines) == 3
        last = klines[-1]
        assert last.code == "00700"
        assert last.open == 469.8
        assert last.close == 457.2
        assert last.high == 475.6
        assert last.low == 455.0
        assert last.market == "hk"
        assert last.source == "eastmoney"


@pytest.mark.asyncio
async def test_get_kline_us():
    """美股 K线"""
    from stock_mcp.adapters.eastmoney import EastmoneyAdapter

    sample = {
        "data": {
            "code": "AAPL",
            "market": 105,
            "name": "苹果",
            "klines": [
                "2026-06-10,290.740,291.580,294.750,287.380,52793266,15384589056.000,2.54,0.35,1.030,0.36",
                "2026-06-11,293.720,295.630,297.000,289.590,42572497,12521172736.000,2.54,1.39,4.050,0.29",
            ],
        }
    }
    with respx.mock() as router:
        router.get(url__regex=r".*push2his\.eastmoney\.com.*kline.*").respond(200, json=sample)
        a = EastmoneyAdapter()
        klines = await a.get_kline("AAPL", "1d", 5, market="us")
        assert len(klines) == 2
        last = klines[-1]
        assert last.code == "AAPL"
        assert last.close == 295.63
        assert last.market == "us"


@pytest.mark.asyncio
async def test_get_kline_a_stock_returns_empty():
    """a_stock K线走别的源"""
    from stock_mcp.adapters.eastmoney import EastmoneyAdapter

    a = EastmoneyAdapter()
    klines = await a.get_kline("600519", "1d", 5, market="a_stock")
    assert klines == []


@pytest.mark.asyncio
async def test_get_kline_unsupported_period():
    from stock_mcp.adapters.eastmoney import EastmoneyAdapter

    a = EastmoneyAdapter()
    with pytest.raises(Exception, match="period"):
        await a.get_kline("00700", "2d", 5, market="hk")


@pytest.mark.asyncio
async def test_get_fundamental_hk_returns_none():
    from stock_mcp.adapters.eastmoney import EastmoneyAdapter

    a = EastmoneyAdapter()
    f = await a.get_fundamental("00700", market="hk")
    assert f is None


@pytest.mark.asyncio
async def test_get_news_hk_returns_empty():
    from stock_mcp.adapters.eastmoney import EastmoneyAdapter

    a = EastmoneyAdapter()
    news = await a.get_news("00700", 5, market="hk")
    assert news == []


# ==== Retry ====
@pytest.mark.asyncio
async def test_get_realtime_quote_502_retries(monkeypatch):
    """eastmoney 端 502 → adapter 重试 3 次, 最终抛 DataSourceError"""
    from unittest.mock import AsyncMock

    from stock_mcp.adapters import eastmoney as em_mod
    from stock_mcp.adapters.eastmoney import EastmoneyAdapter

    call_count = 0

    async def mock_get(*args, **kwargs):
        nonlocal call_count
        call_count += 1
        resp = httpx.Response(502, request=httpx.Request("GET", "https://push2.eastmoney.com"))
        raise httpx.HTTPStatusError("502", request=resp.request, response=resp)

    monkeypatch.setattr(em_mod.asyncio, "sleep", AsyncMock())

    a = EastmoneyAdapter()

    class FakeClient:
        async def __aenter__(self):
            return self

        async def __aexit__(self, *a):
            return None

        async def get(self, *a, **k):
            await mock_get(*a, **k)

    monkeypatch.setattr(em_mod.httpx, "AsyncClient", lambda **k: FakeClient())
    with pytest.raises(em_mod.DataSourceError, match="重试"):
        await a.get_realtime_quote(["00700"], market="hk")
    assert call_count == 3
