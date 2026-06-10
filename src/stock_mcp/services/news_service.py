"""资讯服务"""
import json
from typing import List
from ..domain.models import NewsItem
from ..adapters.registry import AdapterRegistry
from ..cache.sqlite_cache import SQLiteCache
from ..cache.ttl import TTLCalculator


class NewsService:
    def __init__(self, registry: AdapterRegistry, cache: SQLiteCache, ttl_calc: TTLCalculator):
        self._registry = registry
        self._cache = cache
        self._ttl_calc = ttl_calc

    async def get_news(self, code: str, limit: int) -> List[NewsItem]:
        bucket = self._ttl_calc.bucket_for("news")
        key = f"news:{code}:{limit}:{bucket}"
        cached = await self._cache.get(key)
        if cached:
            data = json.loads(cached)
            return [NewsItem.model_validate(item) for item in data]

        items = await self._registry.fan_out("get_news", code=code, limit=limit)
        ttl = self._ttl_calc.ttl_seconds("news")
        await self._cache.set(key, json.dumps([n.model_dump(mode="json") for n in items]), ttl=ttl)
        return items
