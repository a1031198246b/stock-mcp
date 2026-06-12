import pytest
import respx

from stock_mcp.adapters.eastmoney import EastmoneyAdapter

# ==== 资讯 (A 股) ====


@pytest.mark.asyncio
async def test_get_news_eastmoney():
    """模拟东财公告 API (np-anotice-stock 端点)

    真实响应字段:
    - art_code: 公告 ID
    - title: 公告标题
    - notice_date / display_time: 发布时间
    - columns: 栏目分类
    - codes: 关联股票
    """
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
                {
                    "art_code": "AN202606021823168600",
                    "title": "贵州茅台关于回购股份的公告",
                    "notice_date": "2026-05-28 00:00:00",
                    "display_time": "2026-05-28 18:00:00",
                    "columns": [{"column_name": "股份变动"}],
                    "codes": [{"short_name": "贵州茅台"}],
                },
            ]
        }
    }
    with respx.mock() as router:
        router.get(url__regex=r".*np-anotice-stock\.eastmoney\.com.*").respond(200, json=sample)
        a = EastmoneyAdapter()
        news = await a.get_news("600519", limit=10)
        assert len(news) == 2
        assert news[0].title == "贵州茅台2025年度股东会会议资料"
        # source 现在来自 columns[0].column_name
        assert news[0].source == "股东大会资料"
        # URL 应该是 detail 页
        assert "AN202606021823168597" in news[0].url
        # 时间
        assert news[0].publish_time.year == 2026


# ==== 港股 实时 + K线 (新加) ====


@pytest.mark.asyncio
async def test_supported_markets_includes_hk_us():
    """supported_markets 必须含 a_stock/hk/us (新增港美股)"""
    a = EastmoneyAdapter()
    assert "a_stock" in a.supported_markets
    assert "hk" in a.supported_markets
    assert "us" in a.supported_markets


@pytest.mark.asyncio
async def test_get_realtime_quote_hk():
    """港股实时 - 验证字段解析 + market 标记"""
    sample = {
        "data": {
            "total": 4657,
            "diff": [
                {
                    "f2": 469.8,  # 现价
                    "f3": 4.42,  # 涨跌幅%
                    "f4": 19.8,  # 涨跌额
                    "f5": 28580619,  # 成交量
                    "f6": 13202489600.0,  # 成交额
                    "f12": "00700",  # 代码
                    "f14": "腾讯控股",  # 名称
                },
                {
                    "f2": 92.65,
                    "f3": -5.65,
                    "f12": "89988",
                    "f14": "阿里巴巴-WR",
                },
            ],
        }
    }
    with respx.mock() as router:
        router.get(url__regex=r".*push2\.eastmoney\.com.*clist.*").respond(200, json=sample)
        a = EastmoneyAdapter()
        quotes = await a.get_realtime_quote(["00700"], market="hk")
        assert len(quotes) == 1
        q = quotes[0]
        assert q.code == "00700"
        assert q.name == "腾讯控股"
        assert q.price == 469.8
        assert q.change_pct == 4.42
        assert q.market == "hk"
        assert q.source == "eastmoney"


@pytest.mark.asyncio
async def test_get_realtime_quote_us():
    """美股实时"""
    sample = {
        "data": {
            "total": 4465,
            "diff": [
                {
                    "f2": 295.63,
                    "f3": 1.39,
                    "f5": 42572497,
                    "f6": 12521172736.0,
                    "f12": "AAPL",
                    "f14": "苹果",
                }
            ],
        }
    }
    with respx.mock() as router:
        router.get(url__regex=r".*push2\.eastmoney\.com.*clist.*").respond(200, json=sample)
        a = EastmoneyAdapter()
        quotes = await a.get_realtime_quote(["AAPL"], market="us")
        assert len(quotes) == 1
        q = quotes[0]
        assert q.code == "AAPL"
        assert q.name == "苹果"
        assert q.price == 295.63
        assert q.market == "us"


@pytest.mark.asyncio
async def test_get_realtime_quote_filters_by_code():
    """多个股票, 只返回请求的 codes"""
    sample = {
        "data": {
            "diff": [
                {"f2": 100.0, "f12": "00700", "f14": "腾讯"},
                {"f2": 200.0, "f12": "09988", "f14": "阿里"},
                {"f2": 300.0, "f12": "AAPL", "f14": "苹果"},
            ]
        }
    }
    with respx.mock() as router:
        router.get(url__regex=r".*push2\.eastmoney\.com.*clist.*").respond(200, json=sample)
        a = EastmoneyAdapter()
        quotes = await a.get_realtime_quote(["09988"], market="hk")
        assert len(quotes) == 1
        assert quotes[0].code == "09988"


@pytest.mark.asyncio
async def test_get_realtime_quote_a_stock_returns_empty():
    """a_stock 走别的源, adapter 返回空 (不 raise)"""
    a = EastmoneyAdapter()
    quotes = await a.get_realtime_quote(["600519"], market="a_stock")
    assert quotes == []


@pytest.mark.asyncio
async def test_get_realtime_quote_handles_empty_diff():
    """东财返回 diff=[] → 返回空 list 不 crash"""
    sample = {"data": {"total": 0, "diff": []}}
    with respx.mock() as router:
        router.get(url__regex=r".*push2\.eastmoney\.com.*clist.*").respond(200, json=sample)
        a = EastmoneyAdapter()
        quotes = await a.get_realtime_quote(["00700"], market="hk")
        assert quotes == []


@pytest.mark.asyncio
async def test_get_kline_hk():
    """港股 K线 - 验证 kline 字符串解析"""
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
        assert last.period == "1d"


@pytest.mark.asyncio
async def test_get_kline_us():
    """美股 K线"""
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
    """a_stock K线走别的源 (tqcenter/baostock), adapter 返回空"""
    a = EastmoneyAdapter()
    klines = await a.get_kline("600519", "1d", 5, market="a_stock")
    assert klines == []


@pytest.mark.asyncio
async def test_get_kline_unsupported_period():
    """不支持的 period → DataSourceError"""
    a = EastmoneyAdapter()
    with pytest.raises(Exception, match="period"):
        await a.get_kline("00700", "2d", 5, market="hk")


@pytest.mark.asyncio
async def test_get_fundamental_hk_returns_none():
    """港美股基本面暂无, 返回 None (不 raise)"""
    a = EastmoneyAdapter()
    f = await a.get_fundamental("00700", market="hk")
    assert f is None


@pytest.mark.asyncio
async def test_get_news_hk_returns_empty():
    """港美股无公告, 返回空 list (A 股才有)"""
    a = EastmoneyAdapter()
    news = await a.get_news("00700", 5, market="hk")
    assert news == []


@pytest.mark.asyncio
async def test_get_realtime_quote_502_retries(monkeypatch):
    """eastmoney 端 502 → adapter 重试 3 次, 最终抛 DataSourceError"""
    from unittest.mock import AsyncMock

    import httpx

    from stock_mcp.adapters import eastmoney as em_mod

    call_count = 0

    async def mock_get(*args, **kwargs):
        nonlocal call_count
        call_count += 1
        resp = httpx.Response(502, request=httpx.Request("GET", "https://push2.eastmoney.com"))
        raise httpx.HTTPStatusError("502", request=resp.request, response=resp)

    # 跳过 sleep 加速测
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
    assert call_count == 3  # 试了 3 次
