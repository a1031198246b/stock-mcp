from datetime import datetime

import pytest
from pydantic import ValidationError

from stock_mcp.domain.models import (
    Fundamental,
    Kline,
    NewsItem,
    Quote,
    StockQueryResult,
)


def test_quote_full_fields():
    q = Quote(
        code="600519",
        name="贵州茅台",
        price=1500.0,
        change_pct=2.5,
        amount=1.2e9,
        volume=10000,
        open=1480.0,
        high=1510.0,
        low=1475.0,
        last_close=1463.5,
        bid_5=[100, 200, 300, 400, 500],
        ask_5=[150, 250, 350, 450, 550],
        timestamp=datetime(2026, 6, 10, 10, 0, 0),
        source="tqcenter",
    )
    assert q.code == "600519"
    assert q.bid_5[0] == 100


def test_quote_optional_source_default():
    """timestamp 必填, source 可选"""
    with pytest.raises(ValidationError):
        Quote(
            code="600519",
            name="x",
            price=1.0,
            change_pct=0,
            amount=0,
            volume=0,
            open=1,
            high=1,
            low=1,
            last_close=1,
            bid_5=[0] * 5,
            ask_5=[0] * 5,
        )  # 缺 timestamp


def test_kline_fields():
    k = Kline(
        code="600519",
        period="1d",
        datetime=datetime(2026, 6, 10),
        open=100,
        high=105,
        low=99,
        close=103,
        volume=1000000,
        amount=1e8,
    )
    assert k.period == "1d"


def test_fundamental_optional_fields():
    f = Fundamental(code="600519", name="x")
    assert f.pe is None
    assert f.pb is None


def test_news_item_optional_code():
    n = NewsItem(
        code=None,
        title="市场快讯",
        url="https://example.com",
        publish_time=datetime(2026, 6, 10),
        source="eastmoney",
    )
    assert n.code is None


def test_stock_query_result():
    r = StockQueryResult(
        code="600519",
        name="x",
        matched_fields={"ROE": 0.15, "pe": 25.0},
    )
    assert r.matched_fields["ROE"] == 0.15
