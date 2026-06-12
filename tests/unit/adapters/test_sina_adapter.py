import json
from pathlib import Path

import pytest
import respx

from stock_mcp.adapters.sina import SinaAdapter
from stock_mcp.domain.errors import DataSourceError, ParseError


@pytest.fixture
def sina_fixtures():
    fixture = Path("tests/fixtures/sina_realtime.json")
    data = json.loads(fixture.read_text(encoding="utf-8"))
    return {item["code"]: item["raw"] for item in data}


@pytest.mark.asyncio
async def test_get_realtime_quote_parses_sina_format(sina_fixtures):
    with respx.mock() as router:
        router.get(url__regex=r"hq\.sinajs\.cn.*").respond(200, text=sina_fixtures["sh600519"])
        a = SinaAdapter()
        quotes = await a.get_realtime_quote(["600519"])
        assert len(quotes) == 1
        q = quotes[0]
        assert q.code == "600519"
        assert q.price == 1500.0
        assert q.source == "sina"


@pytest.mark.asyncio
async def test_get_realtime_quote_parses_hk(sina_fixtures):
    """港股 18 字段格式 (无五档)"""
    with respx.mock() as router:
        router.get(url__regex=r"hq\.sinajs\.cn.*").respond(200, text=sina_fixtures["hk00700"])
        a = SinaAdapter()
        quotes = await a.get_realtime_quote(["00700"], market="hk")
        assert len(quotes) == 1
        q = quotes[0]
        assert q.code == "00700"
        assert q.name == "腾讯控股"
        assert q.price == 457.2
        # 港股 chg = (now - prev_close) / prev_close * 100
        # (457.2 - 465.6) / 465.6 * 100 = -1.80%
        assert q.change_pct == pytest.approx(-1.80, abs=0.01)
        assert q.bid_5 == [0, 0, 0, 0, 0]  # 港股无五档


@pytest.mark.asyncio
async def test_get_realtime_quote_parses_us(sina_fixtures):
    """美股 ~30 字段格式 (无五档)"""
    with respx.mock() as router:
        router.get(url__regex=r"hq\.sinajs\.cn.*").respond(200, text=sina_fixtures["gb_aapl"])
        a = SinaAdapter()
        quotes = await a.get_realtime_quote(["AAPL"], market="us")
        assert len(quotes) == 1
        q = quotes[0]
        assert q.code == "AAPL"
        assert q.name == "苹果"
        assert q.price == 295.63
        # 美股用 sina 给的 change_pct (fields[2] = 1.39)
        assert q.change_pct == pytest.approx(1.39, abs=0.01)
        assert q.bid_5 == [0, 0, 0, 0, 0]  # 美股无五档


@pytest.mark.asyncio
async def test_get_realtime_quote_handles_404():
    with respx.mock() as router:
        router.get(url__regex=r"hq\.sinajs\.cn.*").respond(404)
        a = SinaAdapter()
        with pytest.raises(DataSourceError):
            await a.get_realtime_quote(["600519"])


@pytest.mark.asyncio
async def test_get_realtime_quote_handles_malformed():
    with respx.mock() as router:
        router.get(url__regex=r"hq\.sinajs\.cn.*").respond(200, text="garbage")
        a = SinaAdapter()
        with pytest.raises(ParseError):
            await a.get_realtime_quote(["600519"])


@pytest.mark.asyncio
async def test_supported_markets_includes_hk_us():
    a = SinaAdapter()
    assert "a_stock" in a.supported_markets
    assert "hk" in a.supported_markets
    assert "us" in a.supported_markets
