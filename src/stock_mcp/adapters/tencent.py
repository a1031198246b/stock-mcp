"""腾讯财经适配器 - A 股/港股/美股 K线 (主力), A 股实时

端点 (集成测试验证 2026-06-12):
- 实时: qt.gtimg.cn/q=sh600519 (仅 A 股, 港美股 v_pv_none_match)
- K线: web.ifzq.gtimg.cn/appstock/app/fqkline/get?param={code},{period},,,{count},{adjust}

**K线 code 格式** (腾讯特有, 不一致):
- A 股: sh600519 / sz000001
- 港股: hk00700
- 美股: usAAPL (us_ 小写 + 代码大写)

**Period 映射**: day / week / month / m5 / m15 / m30 / m60
**Adjust**: qfq 前复权 / 空字符串 不复权
"""

import asyncio
from datetime import datetime
from typing import Any

import httpx
import pandas as pd

from ..domain.errors import DataSourceError
from ..domain.models import Kline, Market, NewsItem, Quote
from .base import BaseAdapter

# 实时 (A 股 only)
_REALTIME_URL = "https://qt.gtimg.cn/q="
# K线
_KLINE_URL = "https://web.ifzq.gtimg.cn/appstock/app/fqkline/get"

# 我们的 period → 腾讯 period
_PERIOD_MAP: dict[str, str] = {
    "1m": "m1",
    "5m": "m5",
    "15m": "m15",
    "30m": "m30",
    "60m": "m60",
    "1d": "day",
    "1w": "week",
    "1M": "month",
}

# market → 腾讯 code 前缀
_MARKET_PREFIX: dict[str, str] = {
    "a_stock_sh": "sh",  # 上海
    "a_stock_sz": "sz",  # 深圳
    "hk": "hk",  # 港股
    "us": "us",  # 美股 (code 大写)
}


def _to_tencent_code(code: str, market: Market) -> str:
    """LLM 短码 → 腾讯 code 格式

    A 股: '600519' → 'sh600519' (上海), '000001' → 'sz000001' (深圳)
    港股: '00700' → 'hk00700'
    美股: 'AAPL' → 'usAAPL' (代码大写)
    """
    c = code.split(".")[0]
    if market == "hk":
        return f"hk{c}"
    if market == "us":
        return f"us{c.upper()}"  # 美股代码大写
    if c.startswith(("60", "68", "11", "13", "9")):
        return f"sh{c}"
    return f"sz{c}"


async def _get_with_retry(url: str, referer: str, retries: int = 3) -> dict[str, Any] | str:
    """GET with retry, 返回 dict (json) 或 str (raw qt.gtimg.cn var=...)

    **注意**: 腾讯 content-type 是 text/html 但 body 是 JSON, 不用 content-type 判断.
    简单 try resp.json(), 失败 fallback 到 text.
    """
    last_exc: Exception | None = None
    for attempt in range(retries):
        try:
            async with httpx.AsyncClient(timeout=10.0) as client:
                resp = await client.get(url, headers={"Referer": referer})
                resp.raise_for_status()
                # 优先试 JSON 解析 (K线, qt 历史)
                try:
                    result: dict[str, Any] = resp.json()
                    return result
                except Exception:
                    # fallback 到 text (qt.gtimg.cn 实时 var=...)
                    return resp.text
        except (httpx.HTTPStatusError, httpx.RequestError) as e:
            last_exc = e
            if attempt < retries - 1:
                await asyncio.sleep(1.5 * (attempt + 1))
    raise DataSourceError(f"tencent 请求失败 ({retries} 次重试): {last_exc}", source="tencent")


class TencentAdapter(BaseAdapter):
    name = "tencent"
    priority = 6  # yfinance(7) 之前的兜底, K线 fallback
    enabled = True
    supported_markets = ["a_stock", "hk", "us"]

    def __init__(self) -> None:
        self._client: httpx.AsyncClient | None = None

    async def _get_client(self) -> httpx.AsyncClient:
        if self._client is None:
            self._client = httpx.AsyncClient(
                timeout=10.0,
                headers={"Referer": "https://gu.qq.com/"},
            )
        return self._client

    # ---- 实时: 仅 A 股 (港美股 qt.gtimg.cn 不通) ----
    async def get_realtime_quote(self, codes: list[str], market: Market = "a_stock") -> list[Quote]:
        if market != "a_stock":
            return []  # 港美股实时走 eastmoney/sina
        tccodes = [_to_tencent_code(c, "a_stock") for c in codes]
        url = f"{_REALTIME_URL}{','.join(tccodes)}"
        try:
            text = await _get_with_retry(url, "https://gu.qq.com/")
        except DataSourceError:
            raise
        except Exception as e:
            raise DataSourceError(f"tencent 实时失败: {e}", source=self.name) from e

        results: list[Quote] = []
        if not isinstance(text, str):
            return results
        for line in text.splitlines():
            line = line.strip()
            if not line or "=" not in line:
                continue
            # v_sh600519="1~贵州茅台~600519~1279.00~1275.88~1272.12~..."
            try:
                kv = line.split('="', 1)
                if len(kv) != 2:
                    continue
                key, payload = kv
                fields = payload.rstrip('";').split("~")
                if len(fields) < 10:
                    continue
                # 字段 0 = "1" 标记, 1=中文名, 2=code, 3=now, 4=prev_close, 5=open,
                # 6=volume, 7=amount_wan, 8-... 五档
                name = fields[1]
                code = fields[2]
                now = float(fields[3] or 0)
                prev_close = float(fields[4] or 0)
                o = float(fields[5] or 0)
                volume = int(float(fields[6] or 0))
                # 五档买卖价 (fields 9-13 买1-5价, 29-33 卖1-5价, 跟 A 股有差异)
                bid_5 = [0] * 5
                ask_5 = [0] * 5
                # 简单拿 5 档买价 (fields 9..13)
                for i in range(min(5, len(fields) - 9)):
                    try:
                        bid_5[i] = int(float(fields[9 + i] or 0))
                    except (ValueError, IndexError):
                        pass
                if now <= 0:
                    continue
                change_pct = ((now - prev_close) / prev_close * 100) if prev_close > 0 else 0
                results.append(
                    Quote(
                        code=code,
                        name=name,
                        price=round(now, 2),
                        change_pct=round(change_pct, 2),
                        amount=float(fields[7] or 0) * 10000,  # 万→元
                        volume=volume,
                        open=o,
                        high=0.0,  # 实时 API 没给 high/low
                        low=0.0,
                        last_close=prev_close,
                        bid_5=bid_5,
                        ask_5=ask_5,
                        timestamp=datetime.now(),
                        source=self.name,
                        market=market,
                    )
                )
            except (ValueError, IndexError):
                continue
        return results

    # ---- K线: A 股 + 港股 + 美股 ----
    async def get_kline(
        self, code: str, period: str, count: int, market: Market = "a_stock"
    ) -> list[Kline]:
        tc_period = _PERIOD_MAP.get(period)
        if not tc_period:
            raise DataSourceError(f"tencent 不支持的 period: {period}", source=self.name)

        tc_code = _to_tencent_code(code, market)
        # 端点: {url}?param={tc_code},{period},,,{count},qfq
        url = f"{_KLINE_URL}?param={tc_code},{tc_period},,,{count},qfq"
        try:
            data = await _get_with_retry(url, "https://gu.qq.com/")
        except DataSourceError:
            raise
        except Exception as e:
            raise DataSourceError(f"tencent K线失败: {e}", source=self.name) from e

        if not isinstance(data, dict) or data.get("code") != 0:
            return []

        stock_data = (data.get("data") or {}).get(tc_code) or {}
        # 优先用 qfqday/qfqweek/..., 退到 day/week/...
        key = f"qfq{tc_period}" if f"qfq{tc_period}" in stock_data else tc_period
        klines_raw = stock_data.get(key) or []
        klines: list[Kline] = []
        for row in klines_raw:
            if not isinstance(row, list) or len(row) < 5:
                continue
            try:
                # 字段: date, open, close, high, low, volume, [可选 amount OR dict 附加信息]
                # **注意**: 港美股 row[6] 是 dict (附加信息), A 股 row[6] 才是 amount
                dt = pd.Timestamp(row[0]).to_pydatetime()
                # amount: 港美股无 (dict), A 股有 (数字)
                amount = 0.0
                if len(row) > 6 and isinstance(row[6], (int, float, str)):
                    try:
                        amount = float(row[6])
                    except (ValueError, TypeError):
                        amount = 0.0
                klines.append(
                    Kline(
                        code=code,
                        period=period,
                        market=market,
                        datetime=dt,
                        open=float(row[1]),
                        close=float(row[2]),
                        high=float(row[3]),
                        low=float(row[4]),
                        volume=int(float(row[5])),
                        amount=amount,
                        source=self.name,
                    )
                )
            except (ValueError, IndexError, TypeError):
                continue
        return klines

    # ---- fundamental/news: 不支持 ----
    async def get_fundamental(self, code: str, market: Market = "a_stock") -> None:
        return None

    async def get_news(self, code: str, limit: int, market: Market = "a_stock") -> list[NewsItem]:
        return []
