"""行情服务 - 编排缓存 + 多源 fallback"""

from ..adapters.registry import AdapterRegistry
from ..cache.sqlite_cache import SQLiteCache
from ..cache.ttl import TTLCalculator
from ..domain.models import Quote


class QuoteService:
    def __init__(
        self,
        registry: AdapterRegistry,
        cache: SQLiteCache,
        ttl_calc: TTLCalculator,
    ):
        self._registry = registry
        self._cache = cache
        self._ttl_calc = ttl_calc

    async def get_realtime_quote(
        self, codes: list[str], market: str = "a_stock"
    ) -> list[Quote]:
        # 0. 选 market 子集
        sub = [
            a
            for a in self._registry.adapters_in_order()
            if a.enabled and market in a.supported_markets
        ]
        if not sub:
            raise ValueError(
                f"market={market} 无可用适配器 (支持: a_stock/hk/us)"
            )

        # 1. 查缓存（按桶）
        bucket = self._ttl_calc.bucket_for("realtime_quote")
        cached = []
        missing = []
        for code in codes:
            key = f"quote:{code}:{bucket}"
            val = await self._cache.get(key)
            if val:
                cached.append(Quote.model_validate_json(val))
            else:
                missing.append(code)

        if not missing:
            return cached

        # 2. 在子集内 fallback
        fresh = await self._registry.fan_out_in_sublist(
            sub, "get_realtime_quote", codes=missing
        )

        # 3. 写缓存
        ttl = self._ttl_calc.ttl_seconds("realtime_quote")
        for q in fresh:
            key = f"quote:{q.code}:{bucket}"
            await self._cache.set(key, q.model_dump_json(), ttl=ttl)

        return cached + fresh
