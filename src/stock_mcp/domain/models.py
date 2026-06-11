"""领域模型 - 所有 adapter 必须输出这些标准化结构"""

from datetime import datetime
from typing import Any, Literal

from pydantic import BaseModel, Field


Market = Literal["a_stock", "hk", "us"]


class Quote(BaseModel):
    code: str
    name: str
    price: float
    change_pct: float  # 涨跌幅 %
    amount: float  # 成交额（元）
    volume: int  # 成交量（手）
    open: float
    high: float
    low: float
    last_close: float
    bid_5: list[int]  # 买一到买五量
    ask_5: list[int]  # 卖一到卖五量
    timestamp: datetime
    source: str = "unknown"
    market: Market = "a_stock"


class Kline(BaseModel):
    code: str
    period: str  # "1m" | "5m" | "15m" | "30m" | "1h" | "1d" | "1w" | "1M"
    datetime: datetime
    open: float
    high: float
    low: float
    close: float
    volume: int
    amount: float
    source: str = "unknown"
    market: Market = "a_stock"


class Fundamental(BaseModel):
    code: str
    name: str
    pe: float | None = None  # 市盈率（TTM）
    pb: float | None = None  # 市净率
    roe: float | None = None  # 净资产收益率
    total_shares: float | None = None  # 总股本（亿股）
    market_cap: float | None = None  # 总市值（亿元）
    industry: str | None = None
    source: str = "unknown"
    market: Market = "a_stock"


class NewsItem(BaseModel):
    code: str | None = None  # None 表示全市场
    title: str
    url: str
    publish_time: datetime
    source: str  # 资讯来源
    summary: str | None = None
    market: Market = "a_stock"


class StockQueryResult(BaseModel):
    """仅 iwencai 用 - 自然语言选股结果"""

    code: str
    name: str
    matched_fields: dict[str, Any] = Field(default_factory=dict)


class FinancialStatement(BaseModel):
    """baostock 财务三表"""
    code: str
    name: str
    market: Market
    period: str  # baostock 原始标识, e.g. "2024-1"
    statement_type: str  # "income" / "balance" / "cashflow"
    data: dict[str, Any] = Field(default_factory=dict)  # 原始字段
    source: str = "baostock"
    fetched_at: datetime
