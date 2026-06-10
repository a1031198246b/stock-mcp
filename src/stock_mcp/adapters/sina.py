"""新浪财经行情适配器"""
import re
from typing import List, Optional
import httpx
import pandas as pd
from ..domain.models import Quote, Kline, Fundamental, NewsItem
from ..domain.errors import DataSourceError, ParseError
from .base import BaseAdapter


# 新浪代码转换: 6 位代码 → sh/sz 前缀
def _to_sina_code(code: str) -> str:
    code = code.split(".")[0]
    if code.startswith(("60", "68", "11", "13")):
        return f"sh{code}"
    return f"sz{code}"


def _parse_sina_line(line: str) -> Optional[Quote]:
    """解析 var hq_str_sh600519="...";"""
    m = re.match(r'var\s+hq_str_([a-z]{2}\d+)="([^"]*)";?', line)
    if not m:
        return None
    symbol, payload = m.groups()
    fields = payload.split(",")
    if len(fields) < 32:
        raise ParseError(f"新浪返回字段不足: {len(fields)}", source="sina")

    code = symbol[2:]  # 去掉 sh/sz
    name = fields[0]
    o, l_close, p, h, low = (float(fields[1]), float(fields[2]),
                             float(fields[3]), float(fields[4]), float(fields[5]))
    last_close = float(fields[2])
    change_pct = ((p - last_close) / last_close * 100) if last_close > 0 else 0

    # 五档买卖量（fields[10..14] 买一到买五, fields[20..24] 卖一到卖五）
    bid_5 = [int(float(fields[10 + i] or 0)) for i in range(5)]
    ask_5 = [int(float(fields[20 + i] or 0)) for i in range(5)]

    return Quote(
        code=code, name=name, price=round(p, 2),
        change_pct=round(change_pct, 2),
        amount=float(fields[9] or 0),       # 成交额
        volume=int(float(fields[8] or 0)),  # 成交量
        open=o, high=h, low=low, last_close=last_close,
        bid_5=bid_5, ask_5=ask_5,
        timestamp=pd.Timestamp.now().to_pydatetime(),
        source="sina",
    )


class SinaAdapter(BaseAdapter):
    name = "sina"
    priority = 2  # 次优先级
    enabled = True

    BASE_URL = "https://hq.sinajs.cn"

    def __init__(self):
        self._client: Optional[httpx.AsyncClient] = None

    async def _get_client(self) -> httpx.AsyncClient:
        if self._client is None:
            self._client = httpx.AsyncClient(
                timeout=10.0,
                headers={"Referer": "https://finance.sina.com.cn"},
            )
        return self._client

    async def get_realtime_quote(self, codes: List[str]) -> List[Quote]:
        sina_codes = [_to_sina_code(c) for c in codes]
        url = f"{self.BASE_URL}/list={','.join(sina_codes)}"
        try:
            client = await self._get_client()
            resp = await client.get(url)
            resp.raise_for_status()
        except httpx.HTTPStatusError as e:
            raise DataSourceError(f"HTTP {e.response.status_code}", source=self.name)
        except Exception as e:
            raise DataSourceError(str(e), source=self.name)

        results = []
        for line in resp.text.strip().splitlines():
            if not line.strip():
                continue
            q = _parse_sina_line(line)
            if q is None:
                raise ParseError("无法解析新浪返回行", source=self.name)
            results.append(q)
        return results

    async def get_kline(self, code, period, count): return []
    async def get_fundamental(self, code): return None
    async def get_news(self, code, limit): return []
