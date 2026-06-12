"""yfinance 适配器 - 港股 + 美股 行情 / K线 / 基本面

yfinance 强项: 全球市场 (美股/港股/欧股), 财经数据全
弱项: 实时 15min 延迟, 国内访问常被墙 (用 HTTP_PROXY 缓解)
"""

from datetime import datetime
from typing import Any

import pandas as pd

from ..domain.errors import DataSourceError
from ..domain.models import (
    Fundamental,
    Kline,
    Market,
    NewsItem,
    Quote,
)
from .base import BaseAdapter

# period 字符串 → yfinance 调 history 的 period 参数
_PERIOD_MAP = {
    "1d": "1y",  # 1d K线, yfinance 一次最多拉 1y
    "1w": "5y",  # 1w K线
    "1M": "10y",  # 1M K线
    "5m": "60d",
    "15m": "60d",
    "30m": "60d",
    "60m": "60d",
    "1m": "7d",
}


def _format_yf_code(code: str, market: str) -> str:
    """LLM 传短码, 适配 yfinance 格式:
    - 港股: 数字 → 'XXXX.HK' (强制 4 位数字, 多余前导 0 截掉)
      '00700' → '0700.HK', '0700' → '0700.HK'
    - 美股: 字母 → 直接用
    - A 股: 不归此函数管 (value_error 早返)
    """
    code = code.strip().upper()
    if market == "hk":
        if code.endswith(".HK"):
            return code
        if code.isdigit() and len(code) <= 5:
            # 港股 yfinance 格式: 4 位数字 .HK (例: 0700.HK)
            # 输入 1-5 位都规范化成 4 位 (多余前导 0 截掉)
            return code[-4:].zfill(4) + ".HK"
        raise ValueError(f"港股代码格式错: {code} (需 1-5 位数字如 00700)")
    if market == "us":
        return code  # 美股直接用
    raise ValueError(f"yfinance 不服务 {market} 市场")


class YfinanceAdapter(BaseAdapter):
    name = "yfinance"
    priority = 7  # 最低 (15min 延迟, 国内被限, 仅海外/有代理兜底)
    enabled = False  # 默认禁用, 初始化成功才启用
    supported_markets = ["hk", "us"]

    def __init__(self) -> None:
        self._yf: Any = None

    def initialize(self) -> None:
        try:
            import yfinance as yf  # type: ignore[import-untyped]
        except ImportError:
            return
        self._yf = yf
        self.enabled = True

    async def get_realtime_quote(self, codes: list[str], market: Market = "us") -> list[Quote]:
        if market not in self.supported_markets:
            raise ValueError(f"yfinance 不服务 {market} 市场 (仅 hk/us)")
        results = []
        for code in codes:
            yf_code = _format_yf_code(code, market)
            try:
                ticker = self._yf.Ticker(yf_code)
                fi = ticker.fast_info
                price = float(fi.last_price) if fi.last_price else 0.0
                last_close = float(fi.previous_close) if fi.previous_close else 0.0
                if price <= 0:
                    continue
                change_pct = ((price - last_close) / last_close * 100) if last_close > 0 else 0.0
                results.append(
                    Quote(
                        code=code,
                        name=yf_code,  # name 暂用 yf_code (info 有 shortName)
                        price=round(price, 4),
                        change_pct=round(change_pct, 2),
                        amount=0.0,
                        volume=0,
                        open=0.0,
                        high=0.0,
                        low=0.0,
                        last_close=last_close,
                        bid_5=[0] * 5,
                        ask_5=[0] * 5,
                        timestamp=datetime.now(),
                        source=self.name,
                        market=market,
                    )
                )
            except Exception as e:
                # 网络失败 (国内访问) — 抛友好错误
                msg = str(e)
                if "Connection" in msg or "timeout" in msg.lower() or "Failed" in msg:
                    raise DataSourceError(
                        f"yfinance 国内访问失败 (code={code}), 请设 HTTP_PROXY 环境变量",
                        source=self.name,
                    ) from e
                raise DataSourceError(str(e), source=self.name) from e
        return results

    async def get_kline(
        self, code: str, period: str, count: int, market: Market = "us"
    ) -> list[Kline]:
        if market not in self.supported_markets:
            raise ValueError(f"yfinance 不服务 {market} 市场")
        yf_period = _PERIOD_MAP.get(period, "1y")
        interval = "1d" if period in ("1d", "1w", "1M") else period
        yf_code = _format_yf_code(code, market)
        try:
            ticker = self._yf.Ticker(yf_code)
            hist = ticker.history(period=yf_period, interval=interval)
        except Exception as e:
            raise DataSourceError(f"yfinance K线失败: {e}", source=self.name) from e
        if hist is None or hist.empty:
            return []
        hist = hist.tail(count)
        klines = []
        for idx, row in hist.iterrows():
            try:
                dt = pd.Timestamp(idx).to_pydatetime(warn=False)
            except Exception:
                dt = datetime.now()
            klines.append(
                Kline(
                    code=code,
                    period=period,
                    market=market,
                    datetime=dt,
                    open=float(row.get("Open", 0)),
                    high=float(row.get("High", 0)),
                    low=float(row.get("Low", 0)),
                    close=float(row.get("Close", 0)),
                    volume=int(float(row.get("Volume", 0))),
                    amount=0.0,
                    source=self.name,
                )
            )
        return klines

    async def get_fundamental(self, code: str, market: Market = "us") -> Fundamental | None:
        if market not in self.supported_markets:
            raise ValueError(f"yfinance 不服务 {market} 市场")
        yf_code = _format_yf_code(code, market)
        try:
            info = self._yf.Ticker(yf_code).info
        except Exception as e:
            raise DataSourceError(f"yfinance info 失败: {e}", source=self.name) from e
        if not info:
            return None
        return Fundamental(
            code=code,
            name=info.get("shortName", yf_code),
            pe=info.get("trailingPE"),
            pb=info.get("priceToBook"),
            roe=info.get("returnOnEquity"),
            total_shares=None,  # yfinance .info 不直接给股数
            market_cap=(info.get("marketCap") or 0) / 1e8 if info.get("marketCap") else None,
            industry=None,
            source=self.name,
            market=market,
        )

    async def get_news(self, code: str, limit: int, market: Market = "us") -> list[NewsItem]:
        if market not in self.supported_markets:
            raise ValueError(f"yfinance 不服务 {market} 市场")
        try:
            news_list = self._yf.Ticker(_format_yf_code(code, market)).news or []
        except Exception:
            return []
        items = []
        for n in news_list[:limit]:
            items.append(
                NewsItem(
                    code=code,
                    market=market,
                    title=n.get("title", ""),
                    url=n.get("link", ""),
                    publish_time=datetime.fromtimestamp(n.get("providerPublishTime", 0)),
                    source=n.get("publisher", "yfinance"),
                    summary=None,
                )
            )
        return items
