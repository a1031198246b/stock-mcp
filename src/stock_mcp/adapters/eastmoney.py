"""东方财富适配器 - 资讯、公告

真实端点: https://np-anotice-stock.eastmoney.com/api/security/ann
(集成测试验证 2026-06-10)
"""

import httpx
import pandas as pd

from ..domain.errors import DataSourceError
from ..domain.models import NewsItem
from .base import BaseAdapter


class EastmoneyAdapter(BaseAdapter):
    name = "eastmoney"
    priority = 4
    enabled = True

    BASE_URL = "https://np-anotice-stock.eastmoney.com/api/security/ann"

    async def get_realtime_quote(self, codes):
        return []

    async def get_kline(self, code, period, count):
        return []

    async def get_fundamental(self, code):
        return None

    async def get_news(self, code: str, limit: int) -> list[NewsItem]:
        """获取公告 (ann_type=A)

        真实响应结构 (验证于 2026-06-10):
        {
          "data": {
            "list": [
              {
                "art_code": "AN202606021823168597",
                "title": "贵州茅台...",
                "notice_date": "2026-06-03 00:00:00",
                "display_time": "2026-06-02 20:07:18:302",
                "columns": [{"column_name": "股东大会资料"}],
                "codes": [{"short_name": "贵州茅台"}]
              }
            ]
          }
        }
        """
        url = (
            f"{self.BASE_URL}"
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

        items = []
        for item in data.get("data", {}).get("list", []):
            try:
                # 解析时间
                publish_time = pd.Timestamp.now().to_pydatetime()
                time_str = item.get("notice_date") or item.get("display_time")
                if time_str:
                    try:
                        publish_time = pd.Timestamp(time_str).to_pydatetime()
                    except Exception:
                        pass

                # 公告 URL
                art_code = item.get("art_code", "")
                detail_url = (
                    f"https://data.eastmoney.com/notices/detail/{art_code}.html" if art_code else ""
                )

                # 来源: 第一列的栏目名
                columns = item.get("columns") or []
                source_name = "东方财富"
                if columns and columns[0].get("column_name"):
                    source_name = columns[0]["column_name"]

                items.append(
                    NewsItem(
                        code=code,
                        title=item.get("title", ""),
                        url=detail_url,
                        publish_time=publish_time,
                        source=source_name,
                    )
                )
            except Exception:
                continue
        return items[:limit]
