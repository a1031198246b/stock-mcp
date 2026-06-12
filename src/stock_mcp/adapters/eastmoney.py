"""东方财富适配器 - A 股/港股/美股 行情 + K线, A 股资讯

A 股: 资讯 (np-anotice-stock)
港美股: 实时 (push2.eastmoney.com clist API), K线 (push2his.eastmoney.com)

端点 (集成测试验证 2026-06-12):
- 资讯: https://np-anotice-stock.eastmoney.com/api/security/ann
- 港股实时: push2.eastmoney.com fs=m:128+t:3,m:128+t:4,m:128+t:1,m:128+t:2
- 美股实时: push2.eastmoney.com fs=m:105,m:106,m:107
- K线: push2his.eastmoney.com secid={market}.{code}  (港股 116, NASDAQ 105, NYSE 106, AMEX 107)

延迟: 港美股 15min (跟 yfinance 一样, 数据源都是东方财富)
**注意**: eastmoney 端 502 偶发, adapter 内置 3 次重试 + 退避
"""

import asyncio
from datetime import datetime

import httpx
import pandas as pd

from ..domain.errors import DataSourceError
from ..domain.models import Kline, Market, NewsItem, Quote
from .base import BaseAdapter

# A 股资讯 (ann_type=A)
_ANN_URL = "https://np-anotice-stock.eastmoney.com/api/security/ann"

# 港美股实时 (clist)
_PUSH2_URL = "https://push2.eastmoney.com/api/qt/clist/get"

# K线
_PUSH2HIS_URL = "https://push2his.eastmoney.com/api/qt/stock/kline/get"

# 各市场 fs 参数 (clist API)
_FS_PARAMS: dict[str, str] = {
    "hk": "m:128+t:3,m:128+t:4,m:128+t:1,m:128+t:2",  # 港股主板
    "us": "m:105,m:106,m:107",  # NYSE/NASDAQ/AMEX
}

# 各市场 secid 前缀 (kline API)
_SECID_PREFIX: dict[str, str] = {
    "hk": "116",  # 港股
    "us_nasdaq": "105",  # NASDAQ
    "us_nyse": "106",  # NYSE
    "us_amex": "107",  # AMEX
}

# yfinance-style period → eastmoney klt 映射
# eastmoney: 101=日, 102=周, 103=月, 5/15/30/60=分钟
_KLT_MAP: dict[str, int] = {
    "1d": 101,
    "1w": 102,
    "1M": 103,
    "5m": 5,
    "15m": 15,
    "30m": 30,
    "60m": 60,
}

# yfinance-style period → kline fields (简单包装, 实际 eastmoney 给全)
_KLINE_FIELDS1 = "f1,f2,f3,f4,f5,f6"
_KLINE_FIELDS2 = "f51,f52,f53,f54,f55,f56,f57,f58,f59,f60,f61"

# HTTP retry 配置
_MAX_RETRIES = 3
_RETRY_BACKOFF = 1.5  # 秒


async def _get_with_retry(client: httpx.AsyncClient, url: str, headers: dict[str, str]) -> dict:
    """GET with 3 次重试 + 指数退避. eastmoney 端 502 偶发.

    **注意**: eastmoney 经常 302 redirect 到 push2delay.eastmoney.com (延迟行情),
    必须 follow_redirects=True 否则拿不到数据.
    """
    last_exc: Exception | None = None
    for attempt in range(_MAX_RETRIES):
        try:
            resp = await client.get(url, headers=headers, follow_redirects=True)
            resp.raise_for_status()
            return resp.json()
        except (httpx.HTTPStatusError, httpx.RequestError) as e:
            last_exc = e
            if attempt < _MAX_RETRIES - 1:
                await asyncio.sleep(_RETRY_BACKOFF * (attempt + 1))
    raise DataSourceError(
        f"eastmoney 请求失败 ({_MAX_RETRIES} 次重试): {last_exc}", source="eastmoney"
    )


def _us_secid_prefix(code: str) -> str:
    """美股代码 → secid 前缀. 默认 NASDAQ (105)."""
    return "105"  # 默认 NASDAQ


class EastmoneyAdapter(BaseAdapter):
    name = "eastmoney"
    priority = 4
    enabled = True
    supported_markets = ["a_stock", "hk", "us"]

    # ---- A 股: 资讯 (原功能) ----
    async def get_news(self, code: str, limit: int, market: Market = "a_stock") -> list[NewsItem]:
        """获取 A 股公告 (港美股无, raise)"""
        if market != "a_stock":
            return []
        url = (
            f"{_ANN_URL}"
            f"?cb=&page_size={limit}&page_index=1"
            f"&ann_type=A&client_source=web&f_node=0&s_node=0"
            f"&stock_list={code}"
        )
        try:
            async with httpx.AsyncClient(timeout=10.0) as client:
                resp = await client.get(url)
                resp.raise_for_status()
                data = resp.json()
        except Exception as e:
            raise DataSourceError(str(e), source=self.name) from e

        items: list[NewsItem] = []
        for item in data.get("data", {}).get("list", []):
            try:
                publish_time: datetime = pd.Timestamp.now().to_pydatetime()
                time_str = item.get("notice_date") or item.get("display_time")
                if time_str:
                    try:
                        publish_time = pd.Timestamp(time_str).to_pydatetime()
                    except Exception:
                        pass
                art_code = item.get("art_code", "")
                detail_url = (
                    f"https://data.eastmoney.com/notices/detail/{art_code}.html" if art_code else ""
                )
                columns = item.get("columns") or []
                source_name = "东方财富"
                if columns and columns[0].get("column_name"):
                    source_name = columns[0]["column_name"]
                items.append(
                    NewsItem(
                        code=code,
                        market=market,
                        title=item.get("title", ""),
                        url=detail_url,
                        publish_time=publish_time,
                        source=source_name,
                    )
                )
            except Exception:
                continue
        return items[:limit]

    # ---- 港美股: 实时 + K线 ----
    async def get_realtime_quote(self, codes: list[str], market: Market = "hk") -> list[Quote]:
        """港美股实时. **逐股并发查 secid** (push2delay pz 最大 100, 拉全市场行不通).

        端点: push2.eastmoney.com/api/qt/stock/get?secid={secid}
        - 港股: secid=116.{code}  (e.g. 116.00700)
        - 美股: secid=105.{code}  (NASDAQ, e.g. 105.AAPL)

        字段 (验证 2026-06-12):
        - f43=high, f44=open, f45=low, f46=last_close (价格 ×100, 港股 3 位小数, 美股 2 位)
        - f47=volume, f48=amount, f60=now (价格 ×100)
        - f169=change (价格 ×100), f170=change_pct (×100, e.g. 1.39% = 139), f171=turnover

        性能: N 只股票用 asyncio.gather 并发, 单次连接复用.
        """
        if market not in ("hk", "us"):
            return []  # A 股走别的源
        secid_prefix = _SECID_PREFIX["hk"] if market == "hk" else _us_secid_prefix("dummy")
        # fields 一次拿全
        fields = "f43,f44,f45,f46,f47,f48,f60,f169,f170,f171"

        async def _fetch_one(client: httpx.AsyncClient, code: str) -> Quote | None:
            secid = f"{secid_prefix}.{code}"
            url = f"https://push2.eastmoney.com/api/qt/stock/get?secid={secid}&fields={fields}"
            # DataSourceError 让它 propagate, 由 gather + 上层处理
            # (只有"网络通但单只股票没数据"才 return None, 整端挂要 raise)
            data = await _get_with_retry(client, url, {"Referer": "https://quote.eastmoney.com/"})
            d = data.get("data") or {}
            if not d or not d.get("f60"):
                return None  # 无数据 (停牌/不存在)
            try:
                # 价格精度: 港股 3 位小数 (457.200) → f60=457200 (6 位) ÷1000
                #          美股 2 位小数 (295.63)  → f60=29563 (5 位) ÷100
                # 启发: f60 >= 100000 (6 位) 用 ÷1000, 否则 ÷100
                now_raw = float(d.get("f60") or 0)
                if now_raw <= 0:
                    return None
                divisor = 1000.0 if now_raw >= 100000 else 100.0
                now = now_raw / divisor
                chg_pct = float(d.get("f170") or 0) / 100.0  # eastmoney 涨跌幅 ×100
                high = float(d.get("f43") or 0) / divisor
                o = float(d.get("f44") or 0) / divisor
                low = float(d.get("f45") or 0) / divisor
                last_close = float(d.get("f46") or 0) / divisor
                volume = int(float(d.get("f47") or 0))
                amount = float(d.get("f48") or 0)
                return Quote(
                    code=code.upper(),
                    name=code,  # 单股查询不返回 name, 用 code 占位
                    price=round(now, 4),
                    change_pct=round(chg_pct, 2),
                    amount=amount,
                    volume=volume,
                    open=round(o, 4),
                    high=round(high, 4),
                    low=round(low, 4),
                    last_close=round(last_close, 4),
                    bid_5=[0] * 5,
                    ask_5=[0] * 5,
                    timestamp=datetime.now(),
                    source=self.name,
                    market=market,
                )
            except (ValueError, TypeError):
                return None

        try:
            async with httpx.AsyncClient(timeout=10.0) as client:
                results = await asyncio.gather(
                    *[_fetch_one(client, c) for c in codes],
                    return_exceptions=True,
                )
        except Exception as e:
            raise DataSourceError(f"eastmoney 实时失败: {e}", source=self.name) from e
        # 收集有效 Quote, 如果有 DataSourceError 抛出第一个
        quotes: list[Quote] = []
        for r in results:
            if isinstance(r, DataSourceError):
                raise r
            if r is not None:
                quotes.append(r)
        return quotes

    async def get_kline(
        self, code: str, period: str, count: int, market: Market = "hk"
    ) -> list[Kline]:
        """港美股 K线.

        kline 端点返回 (验证 2026-06-12):
        {
          "data": {
            "code": "00700", "market": 116, "name": "腾讯控股",
            "klines": [
              "2026-06-11,469.800,457.200,475.600,455.000,28580619,13202489600.000,...",
              # 字段: date,open,close,high,low,volume,amount,...
            ]
          }
        }
        """
        if market not in ("hk", "us"):
            return []
        klt = _KLT_MAP.get(period)
        if not klt:
            raise DataSourceError(f"eastmoney 不支持的 period: {period}", source=self.name)
        secid_prefix = _SECID_PREFIX["hk"] if market == "hk" else _us_secid_prefix(code)
        secid = f"{secid_prefix}.{code}"
        url = (
            f"{_PUSH2HIS_URL}?secid={secid}"
            f"&fields1={_KLINE_FIELDS1}&fields2={_KLINE_FIELDS2}"
            f"&klt={klt}&fqt=1&end=20500000&lmt={count}"
        )
        try:
            async with httpx.AsyncClient(timeout=10.0) as client:
                data = await _get_with_retry(
                    client, url, {"Referer": "https://quote.eastmoney.com/"}
                )
        except DataSourceError:
            raise
        except Exception as e:
            raise DataSourceError(f"eastmoney K线失败: {e}", source=self.name) from e

        d = data.get("data") or {}
        klines_raw: list[str] = d.get("klines") or []
        klines: list[Kline] = []
        for line in klines_raw:
            try:
                # "2026-06-11,469.800,457.200,475.600,455.000,28580619,13202489600.000,..."
                parts = line.split(",")
                if len(parts) < 7:
                    continue
                dt = pd.Timestamp(parts[0]).to_pydatetime()
                klines.append(
                    Kline(
                        code=code,
                        period=period,
                        market=market,
                        datetime=dt,
                        open=float(parts[1]),
                        close=float(parts[2]),
                        high=float(parts[3]),
                        low=float(parts[4]),
                        volume=int(float(parts[5])),
                        amount=float(parts[6]),
                        source=self.name,
                    )
                )
            except (ValueError, IndexError, TypeError):
                continue
        return klines

    # ---- 港美股暂无 ----
    async def get_fundamental(self, code: str, market: Market = "hk") -> None:
        """港美股基本面暂无, raise (上层 fallback)"""
        if market != "a_stock":
            return None
        return None
