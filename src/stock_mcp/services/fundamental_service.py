"""基本面服务"""

from typing import cast

from ..adapters.registry import AdapterRegistry
from ..cache.sqlite_cache import SQLiteCache
from ..cache.ttl import TTLCalculator
from ..domain.models import Fundamental


class FundamentalService:
    def __init__(self, registry: AdapterRegistry, cache: SQLiteCache, ttl_calc: TTLCalculator):
        self._registry = registry
        self._cache = cache
        self._ttl_calc = ttl_calc

    async def get_fundamental(self, code: str, market: str = "a_stock") -> Fundamental | None:
        # 0. 选 market 子集
        sub = [
            a
            for a in self._registry.adapters_in_order()
            if a.enabled and market in a.supported_markets
        ]
        if not sub:
            raise ValueError(f"market={market} 无可用适配器 (支持: a_stock/hk/us)")

        key = f"fundamental:{code}"
        cached = await self._cache.get(key)
        if cached:
            return Fundamental.model_validate_json(cached)

        result = await self._registry.fan_out_in_sublist(
            sub, "get_fundamental", code=code, market=market
        )
        if result:
            ttl = self._ttl_calc.ttl_seconds("fundamental")
            await self._cache.set(key, result.model_dump_json(), ttl=ttl)
        return cast(Fundamental | None, result)
