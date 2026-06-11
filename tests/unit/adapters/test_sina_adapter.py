import json
from pathlib import Path

import pytest
import respx

from stock_mcp.adapters.sina import SinaAdapter
from stock_mcp.domain.errors import DataSourceError, ParseError


@pytest.fixture
def sina_raw():
    fixture = Path("tests/fixtures/sina_realtime.json")
    data = json.loads(fixture.read_text())
    return data[0]["raw"]


@pytest.mark.asyncio
async def test_get_realtime_quote_parses_sina_format(sina_raw):
    with respx.mock() as router:
        router.get(url__regex=r"hq\.sinajs\.cn.*").respond(200, text=sina_raw)
        a = SinaAdapter()
        quotes = await a.get_realtime_quote(["600519"])
        assert len(quotes) == 1
        q = quotes[0]
        assert q.code == "600519"
        assert q.price == 1500.0
        assert q.source == "sina"


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
