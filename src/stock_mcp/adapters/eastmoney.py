"""东方财富适配器 - 资讯、公告"""
from typing import List
import httpx
import pandas as pd
from ..domain.models import Quote, Kline, Fundamental, NewsItem
from ..domain.errors import DataSourceError
from .base import BaseAdapter


class EastmoneyAdapter(BaseAdapter):
    name = "eastmoney"
    priority = 4
    enabled = True

    BASE_URL = "https://np-anotice-stock.eastmoney.com/api/security/ann"

    async def get_realtime_quote(self, codes): return []
    async def get_kline(self, code, period, count): return []
    async def get_fundamental(self, code): return None

    async def get_news(self, code: str, limit: int) -> List[NewsItem]:
        # 简化: 直接走东财公告/新闻 API (push2 走资讯频道)
        url = (
            f"https://push2.eastmoney.com/api/news/list"
            f"?cb=&page_size={limit}&page_index=1&client=web&biz=news"
            f"&stock_list={code}"
        )
        try:
            async with httpx.AsyncClient(timeout=10.0) as client:
                resp = await client.get(url)
                resp.raise_for_status()
                data = resp.json()
        except Exception as e:
            raise DataSourceError(str(e), source=self.name)

        items = []
        for item in data.get("data", {}).get("list", []):
            try:
                publish_time = pd.Timestamp.now().to_pydatetime()
                if item.get("showTime"):
                    try:
                        publish_time = pd.Timestamp(item["showTime"]).to_pydatetime()
                    except Exception:
                        pass
                items.append(NewsItem(
                    code=code,
                    title=item.get("title", ""),
                    url=item.get("url", ""),
                    publish_time=publish_time,
                    source=item.get("mediaName", "东方财富"),
                ))
            except Exception:
                continue
        return items[:limit]
