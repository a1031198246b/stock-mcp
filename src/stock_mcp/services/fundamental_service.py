"""基本面服务"""

from ..adapters.registry import AdapterRegistry
from ..cache.sqlite_cache import SQLiteCache
from ..cache.ttl import TTLCalculator
from ..domain.models import Fundamental


class FundamentalService:
    def __init__(self, registry: AdapterRegistry, cache: SQLiteCache, ttl_calc: TTLCalculator):
        self._registry = registry
        self._cache = cache
        self._ttl_calc = ttl_calc

    async def get_fundamental(self, code: str) -> Fundamental | None:
        key = f"fundamental:{code}"
        cached = await self._cache.get(key)
        if cached:
            return Fundamental.model_validate_json(cached)

        result = await self._registry.fan_out("get_fundamental", code=code)
        if result:
            ttl = self._ttl_calc.ttl_seconds("fundamental")
            await self._cache.set(key, result.model_dump_json(), ttl=ttl)
        return result
