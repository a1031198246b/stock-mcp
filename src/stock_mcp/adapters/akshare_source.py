"""AKShare 适配器 - 基本面、K线补全、资讯"""

import pandas as pd

from ..domain.errors import DataSourceError
from ..domain.models import Fundamental, Kline, NewsItem, Quote
from .base import BaseAdapter

try:
    import akshare as ak
except ImportError:
    ak = None  # type: ignore


class AkshareAdapter(BaseAdapter):
    name = "akshare"
    priority = 3
    enabled = ak is not None

    async def get_realtime_quote(self, codes: list[str], market: str = "a_stock") -> list[Quote]:
        """akshare 不擅长实时行情, 让位给 tqcenter / sina"""
        return []

    async def get_kline(self, code: str, period: str, count: int, market: str = "a_stock") -> list[Kline]:
        if ak is None:
            raise DataSourceError("akshare 未安装", source=self.name)
        try:
            df = ak.stock_zh_a_hist(
                symbol=code,
                period={"1d": "daily", "1w": "weekly", "1M": "monthly"}.get(period, "daily"),
                adjust="qfq",
                count=count,
            )
        except Exception as e:
            raise DataSourceError(str(e), source=self.name) from e

        klines = []
        for _, row in df.iterrows():
            klines.append(
                Kline(
                    code=code,
                    period=period,
                    datetime=pd.Timestamp(row["日期"]).to_pydatetime(),
                    open=float(row["开盘"]),
                    high=float(row["最高"]),
                    low=float(row["最低"]),
                    close=float(row["收盘"]),
                    volume=int(float(row["成交量"])),
                    amount=float(row["成交额"]),
                    source=self.name,
                )
            )
        return klines

    async def get_fundamental(self, code: str, market: str = "a_stock") -> Fundamental | None:
        if ak is None:
            raise DataSourceError("akshare 未安装", source=self.name)
        try:
            df = ak.stock_a_indicator_lg(symbol=code)
        except Exception as e:
            raise DataSourceError(str(e), source=self.name) from e

        if df.empty:
            return None
        row = df.iloc[0]
        return Fundamental(
            code=code,
            name="",
            pe=_safe_float(row.get("pe")),
            pb=_safe_float(row.get("pb")),
            roe=None,  # akshare 的 indicator 不直接给
            total_shares=_safe_float(row.get("总股本")),
            market_cap=_safe_float(row.get("总市值")),
            industry=None,
            source=self.name,
        )

    async def get_news(self, code: str, limit: int, market: str = "a_stock") -> list[NewsItem]:
        if ak is None:
            return []
        try:
            ak.stock_news_em(symbol=code)
        except Exception as e:
            raise DataSourceError(str(e), source=self.name) from e
        # P3 阶段再细化
        return []


def _safe_float(v) -> float | None:
    try:
        if v is None or (isinstance(v, float) and pd.isna(v)):
            return None
        return float(v)
    except Exception:
        return None
