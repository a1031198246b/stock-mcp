"""新浪财经行情适配器 - A 股 + 港股 + 美股

端点 (集成测试验证 2026-06-12):
- A 股: hq.sinajs.cn/list=sh600519 (32 字段, 含五档)
- 港股: hq.sinajs.cn/list=hk00700 (18 字段, 无五档)
- 美股: hq.sinajs.cn/list=gb_aapl  (~30 字段, 无五档)

国内无需代理. 缺点: K线 API 港美股返回 null (走 eastmoney 兜底).
"""

import re

import httpx
import pandas as pd

from ..domain.errors import DataSourceError, ParseError
from ..domain.models import Quote
from .base import BaseAdapter

# 腾讯财经 K线 API (港美股 + A 股, 跟 sina 互补)
_TENCENT_KLINE_URL = "https://web.ifzq.gtimg.cn/appstock/app/fqkline/get"


def _to_sina_code(code: str, market: str) -> str:
    """6 位代码 → 新浪前缀 (按 market 区分)"""
    c = code.split(".")[0]
    if market == "hk":
        # 港股: 5 位数字 (00700) → hk00700
        return f"hk{c}"
    if market == "us":
        # 美股: 字母 (AAPL) → gb_aapl (小写)
        return f"gb_{c.lower()}"
    # a_stock: 原逻辑
    if c.startswith(("60", "68", "11", "13")):
        return f"sh{c}"
    return f"sz{c}"


def _parse_sina_line(line: str) -> Quote | None:
    """解析 var hq_str_{prefix}{code}="..."; → Quote (按 prefix 走不同解析)

    A 股 (sh/sz): 32 字段, 含五档买卖
    港股 (hk):    18 字段, 无五档
    美股 (gb_):  ~30 字段, 无五档 (prefix 含下划线, e.g. "gb_aapl")
    """
    # 美股 prefix 是 "gb_", A 股/港股 是 2 字母
    if line.startswith("var hq_str_gb_"):
        prefix = "gb"
        m = re.match(r'var\s+hq_str_(gb)_([^=]+)="([^"]*)";?', line)
    else:
        prefix = "hk" if "hq_str_hk" in line else "astock"
        m = re.match(r'var\s+hq_str_([a-z]{2})([^=]+)="([^"]*)";?', line)
    if not m:
        return None
    _, code, payload = m.groups()
    fields = payload.split(",")
    base_code = code  # 原始 6 位或字母

    if prefix == "astock":
        # A 股 32 字段格式
        if len(fields) < 32:
            raise ParseError(f"新浪 A 股字段不足: {len(fields)}", source="sina")
        name = fields[0]
        o, p, h, low = (
            float(fields[1]),
            float(fields[3]),
            float(fields[4]),
            float(fields[5]),
        )
        last_close = float(fields[2])
        bid_5 = [int(float(fields[10 + i] or 0)) for i in range(5)]
        ask_5 = [int(float(fields[20 + i] or 0)) for i in range(5)]
        volume = int(float(fields[8] or 0)) // 100
        amount = float(fields[9] or 0)
    elif prefix == "hk":
        # 港股 18 字段
        if len(fields) < 18:
            raise ParseError(f"新浪港股字段不足: {len(fields)}", source="sina")
        name = fields[1] if fields[1] else fields[0]
        o = float(fields[2])
        prev_close = float(fields[3])
        h = float(fields[4])
        low = float(fields[5])
        p = float(fields[6])
        last_close = prev_close
        volume = int(float(fields[12] or 0))
        amount = float(fields[11] or 0)
        bid_5 = [0] * 5
        ask_5 = [0] * 5
    elif prefix == "gb":
        # 美股 ~30 字段 (验证 2026-06-12 收盘):
        # [0]name_cn [1]now [2]change_pct [3]datetime [4]change [5]open
        # [6]high [7]low [8]52w_high [9]52w_low [10]volume ...
        # [22]prev_close (前日收盘, 盘前数据可能错位到其他含义, 故不依赖)
        if len(fields) < 12:
            raise ParseError(f"新浪美股字段不足: {len(fields)}", source="sina")
        name = fields[0]
        p = float(fields[1])
        # 直接用 sina 给的 change_pct, 避免盘前字段错位算 chg 错
        change_pct_sina = float(fields[2] or 0)
        o = float(fields[5])
        h = float(fields[6])
        low = float(fields[7])
        # prev_close 反推: now - change, 找不到 change 就 0
        try:
            change = float(fields[4] or 0)
            prev_close = p - change
        except (ValueError, IndexError):
            prev_close = 0.0
        last_close = prev_close
        volume = int(float(fields[10] or 0))
        amount = 0.0
        bid_5 = [0] * 5
        ask_5 = [0] * 5
    else:
        raise ParseError(f"未知市场前缀: {prefix}", source="sina")

    # A 股/港股 自己算 chg_pct; 美股用 sina 给的 (字段错位风险)
    if prefix == "gb":
        change_pct = change_pct_sina
    else:
        change_pct = ((p - last_close) / last_close * 100) if last_close > 0 else 0

    return Quote(
        code=base_code.upper(),  # 美股 AAPL 转大写
        name=name,
        price=round(p, 2 if prefix != "gb" else 4),
        change_pct=round(change_pct, 2),
        amount=amount,
        volume=volume,
        open=o,
        high=h,
        low=low,
        last_close=last_close,
        bid_5=[v // 100 for v in bid_5],  # A 股: 股→手
        ask_5=[v // 100 for v in ask_5],
        timestamp=pd.Timestamp.now().to_pydatetime(),
        source="sina",
    )


class SinaAdapter(BaseAdapter):
    name = "sina"
    priority = 2
    enabled = True
    supported_markets = ["a_stock", "hk", "us"]

    BASE_URL = "https://hq.sinajs.cn"

    def __init__(self):
        self._client: httpx.AsyncClient | None = None

    async def _get_client(self) -> httpx.AsyncClient:
        if self._client is None:
            self._client = httpx.AsyncClient(
                timeout=10.0,
                headers={"Referer": "https://finance.sina.com.cn"},
            )
        return self._client

    async def get_realtime_quote(self, codes: list[str], market: str = "a_stock") -> list[Quote]:
        sina_codes = [_to_sina_code(c, market) for c in codes]
        url = f"{self.BASE_URL}/list={','.join(sina_codes)}"
        try:
            client = await self._get_client()
            resp = await client.get(url)
            resp.raise_for_status()
        except httpx.HTTPStatusError as e:
            raise DataSourceError(f"HTTP {e.response.status_code}", source=self.name) from e
        except Exception as e:
            raise DataSourceError(str(e), source=self.name) from e

        results = []
        for line in resp.text.strip().splitlines():
            if not line.strip():
                continue
            q = _parse_sina_line(line)
            if q is None:
                raise ParseError("无法解析新浪返回行", source=self.name)
            results.append(q)
        return results

    async def get_kline(self, code, period, count, market: str = "a_stock"):
        # 港美股 K线 JSON 不支持 (走 eastmoney 兜底)
        return []

    async def get_fundamental(self, code, market: str = "a_stock"):
        return None

    async def get_news(self, code, limit, market: str = "a_stock"):
        return []
