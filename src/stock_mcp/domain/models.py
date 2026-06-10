"""领域模型 - 所有 adapter 必须输出这些标准化结构"""
from datetime import datetime
from typing import Optional, List, Dict, Any
from pydantic import BaseModel, Field


class Quote(BaseModel):
    code: str
    name: str
    price: float
    change_pct: float          # 涨跌幅 %
    amount: float              # 成交额（元）
    volume: int                # 成交量（手）
    open: float
    high: float
    low: float
    last_close: float
    bid_5: List[int]           # 买一到买五量
    ask_5: List[int]           # 卖一到卖五量
    timestamp: datetime
    source: str = "unknown"


class Kline(BaseModel):
    code: str
    period: str                # "1m" | "5m" | "15m" | "30m" | "1h" | "1d" | "1w" | "1M"
    datetime: datetime
    open: float
    high: float
    low: float
    close: float
    volume: int
    amount: float
    source: str = "unknown"


class Fundamental(BaseModel):
    code: str
    name: str
    pe: Optional[float] = None            # 市盈率（TTM）
    pb: Optional[float] = None            # 市净率
    roe: Optional[float] = None           # 净资产收益率
    total_shares: Optional[float] = None  # 总股本（亿股）
    market_cap: Optional[float] = None    # 总市值（亿元）
    industry: Optional[str] = None
    source: str = "unknown"


class NewsItem(BaseModel):
    code: Optional[str] = None    # None 表示全市场
    title: str
    url: str
    publish_time: datetime
    source: str                   # 资讯来源
    summary: Optional[str] = None


class StockQueryResult(BaseModel):
    """仅 iwencai 用 - 自然语言选股结果"""
    code: str
    name: str
    matched_fields: Dict[str, Any] = Field(default_factory=dict)
