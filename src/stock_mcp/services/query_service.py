"""查询服务 - 自然语言选股"""
from typing import List
from ..domain.models import StockQueryResult
from ..domain.errors import DataSourceError
from ..adapters.iwencai import IwencaiAdapter


class QueryService:
    def __init__(self, iwencai: IwencaiAdapter):
        self._iwencai = iwencai

    async def query_stocks(self, condition: str) -> List[StockQueryResult]:
        if not self._iwencai.enabled:
            raise DataSourceError("iwencai 适配器未启用, 请在 .env 中配置 IWENCAI_COOKIE",
                                  source="iwencai")
        return await self._iwencai.query_stocks(condition)
