"""资讯服务 - 不 cache

**2026-06-12 简化**: news 不 cache. 资讯用户不反复查, 10 分钟 TTL 命中率低.
"""

from typing import cast

from ..adapters.registry import AdapterRegistry
from ..cache.sqlite_cache import SQLiteCache  # 保留依赖
from ..cache.ttl import TTLCalculator  # 保留依赖
from ..domain.models import NewsItem


class NewsService:
    def __init__(self, registry: AdapterRegistry, cache: SQLiteCache, ttl_calc: TTLCalculator):
        self._registry = registry
        self._cache = cache
        self._ttl_calc = ttl_calc

    async def get_news(self, code: str, limit: int, market: str = "a_stock") -> list[NewsItem]:
        # 0. 选 market 子集
        sub = [
            a
            for a in self._registry.adapters_in_order()
            if a.enabled and market in a.supported_markets
        ]
        if not sub:
            raise ValueError(f"market={market} 无可用适配器 (支持: a_stock/hk/us)")

        return cast(
            list[NewsItem],
            await self._registry.fan_out_in_sublist(
                sub, "get_news", code=code, limit=limit, market=market
            ),
        )
