"""TencentAdapter 单测 (respx mock)"""

import pytest
import respx

from stock_mcp.adapters.tencent import TencentAdapter, _to_tencent_code


def test_to_tencent_code_a_stock():
    """A 股: 60/68 → sh, 00/30 → sz"""
    assert _to_tencent_code("600519", "a_stock") == "sh600519"
    assert _to_tencent_code("000001", "a_stock") == "sz000001"
    assert _to_tencent_code("300750", "a_stock") == "sz300750"


def test_to_tencent_code_hk():
    """港股: 数字 → hk{code}"""
    assert _to_tencent_code("00700", "hk") == "hk00700"
    assert _to_tencent_code("09988", "hk") == "hk09988"


def test_to_tencent_code_us():
    """美股: 字母 → us{code} (代码大写)"""
    assert _to_tencent_code("AAPL", "us") == "usAAPL"
    assert _to_tencent_code("tsla", "us") == "usTSLA"  # 小写转大写


def test_supported_markets_includes_all_three():
    a = TencentAdapter()
    assert "a_stock" in a.supported_markets
    assert "hk" in a.supported_markets
    assert "us" in a.supported_markets


# ==== 实时 (A 股) ====


@pytest.mark.asyncio
async def test_get_realtime_quote_a_stock():
    """A 股实时: qt.gtimg.cn 返 v_sh600519="1~贵州茅台~600519~1279.00~...";"""
    raw = (
        'v_sh600519="1~贵州茅台~600519~1279.000~1275.880~1272.120~'
        "25352~3230008220~1278.99~15~1278.98~4~1278.97~1~1278.52~1~"
        '1278.29~1~1279.00~57~1279.01~1~1279.02~4~1279.10~3~1279.18~1"'
    )
    with respx.mock() as router:
        router.get(url__regex=r"qt\.gtimg\.cn.*").respond(200, text=raw)
        a = TencentAdapter()
        quotes = await a.get_realtime_quote(["600519"], market="a_stock")
        assert len(quotes) == 1
        q = quotes[0]
        assert q.code == "600519"
        assert q.name == "贵州茅台"
        assert q.price == 1279.0
        # chg = (1279 - 1275.88) / 1275.88 * 100 ≈ 0.24
        assert q.change_pct == pytest.approx(0.244, abs=0.01)


@pytest.mark.asyncio
async def test_get_realtime_quote_hk_returns_empty():
    """港股 qt.gtimg.cn 不通, 返回空 list (走 eastmoney/sina)"""
    a = TencentAdapter()
    quotes = await a.get_realtime_quote(["00700"], market="hk")
    assert quotes == []


@pytest.mark.asyncio
async def test_get_realtime_quote_us_returns_empty():
    a = TencentAdapter()
    quotes = await a.get_realtime_quote(["AAPL"], market="us")
    assert quotes == []


@pytest.mark.asyncio
async def test_get_realtime_quote_handles_no_data():
    """qt.gtimg.cn 返 v_pv_none_match=1 → 不 crash, 返回空"""
    raw = 'v_pv_none_match="1";'
    with respx.mock() as router:
        router.get(url__regex=r"qt\.gtimg\.cn.*").respond(200, text=raw)
        a = TencentAdapter()
        quotes = await a.get_realtime_quote(["SH600519"], market="a_stock")
        assert quotes == []


# ==== K线 ====


@pytest.mark.asyncio
async def test_get_kline_a_stock():
    """A 股 K线: qfqday 字段"""
    sample = {
        "code": 0,
        "msg": "",
        "data": {
            "sh600519": {
                "qfqday": [
                    ["2026-06-09", "1262.99", "1256.0", "1263.0", "1252.55", "27860"],
                    ["2026-06-10", "1252.08", "1275.88", "1282.0", "1250.21", "39244"],
                    ["2026-06-11", "1272.12", "1279.0", "1282.88", "1266.91", "25352"],
                ],
                "qt": {},
            }
        },
    }
    with respx.mock() as router:
        router.get(url__regex=r"web\.ifzq\.gtimg\.cn.*").respond(200, json=sample)
        a = TencentAdapter()
        klines = await a.get_kline("600519", "1d", 3, market="a_stock")
        assert len(klines) == 3
        last = klines[-1]
        assert last.code == "600519"
        assert last.open == 1272.12
        assert last.close == 1279.0
        assert last.market == "a_stock"
        assert last.source == "tencent"


@pytest.mark.asyncio
async def test_get_kline_hk_uses_day_field():
    """港股 K线: 没有 qfqday, 用 day 字段 + row[6] 是 dict (附加信息)"""
    sample = {
        "code": 0,
        "msg": "",
        "data": {
            "hk00700": {
                "day": [
                    [
                        "2026-06-09",
                        "443.800",
                        "453.200",
                        "468.400",
                        "443.200",
                        "37387399",
                        {
                            "cqr": "2026-06-09",
                            "FHcontent": "",
                            "HGcontent": "回购109万股",
                        },
                    ],
                    [
                        "2026-06-10",
                        "454.800",
                        "465.600",
                        "471.000",
                        "451.600",
                        "35788237",
                        {"cqr": "2026-06-10"},
                    ],
                ],
                "qt": {},
            }
        },
    }
    with respx.mock() as router:
        router.get(url__regex=r"web\.ifzq\.gtimg\.cn.*").respond(200, json=sample)
        a = TencentAdapter()
        klines = await a.get_kline("00700", "1d", 5, market="hk")
        assert len(klines) == 2
        assert klines[0].code == "00700"
        assert klines[0].open == 443.8
        assert klines[0].close == 453.2
        assert klines[0].volume == 37387399
        # amount 应该是 0 (港股 row[6] 是 dict, 不解析)
        assert klines[0].amount == 0.0
        assert klines[0].market == "hk"


@pytest.mark.asyncio
async def test_get_kline_us():
    """美股 K线: 验证大写代码 usAAPL"""
    sample = {
        "code": 0,
        "msg": "",
        "data": {
            "usAAPL": {"day": [["2026-06-11", "293.72", "295.63", "297.0", "289.59", "42572497"]]}
        },
    }
    with respx.mock() as router:
        # 验证请求 URL 含 usAAPL (大写)
        router.get(url__regex=r"web\.ifzq\.gtimg\.cn.*").respond(200, json=sample)
        a = TencentAdapter()
        klines = await a.get_kline("AAPL", "1d", 5, market="us")
        assert len(klines) == 1
        assert klines[0].code == "AAPL"
        assert klines[0].market == "us"
        # 验证 url 用了 usAAPL
        last_url = str(router.calls.last.request.url)
        assert "usAAPL" in last_url, f"url 应该含 usAAPL, 实际: {last_url}"


@pytest.mark.asyncio
async def test_get_kline_unsupported_period():
    """不支持的 period → DataSourceError"""
    a = TencentAdapter()
    with pytest.raises(Exception, match="period"):
        await a.get_kline("600519", "2d", 5, market="a_stock")


@pytest.mark.asyncio
async def test_get_kline_empty_response():
    """返回 code != 0 → 空 list 不 crash"""
    sample = {"code": 1, "msg": "error", "data": {}}
    with respx.mock() as router:
        router.get(url__regex=r"web\.ifzq\.gtimg\.cn.*").respond(200, json=sample)
        a = TencentAdapter()
        klines = await a.get_kline("600519", "1d", 5, market="a_stock")
        assert klines == []


@pytest.mark.asyncio
async def test_get_fundamental_returns_none():
    a = TencentAdapter()
    f = await a.get_fundamental("600519", "a_stock")
    assert f is None


@pytest.mark.asyncio
async def test_get_news_returns_empty():
    a = TencentAdapter()
    news = await a.get_news("600519", 5, "a_stock")
    assert news == []
