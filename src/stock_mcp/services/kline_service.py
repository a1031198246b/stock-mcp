"""K线服务"""

from ..adapters.registry import AdapterRegistry
from ..cache.sqlite_cache import SQLiteCache
from ..cache.ttl import TTLCalculator
from ..domain.models import Kline


class KlineService:
    def __init__(self, registry: AdapterRegistry, cache: SQLiteCache, ttl_calc: TTLCalculator):
        self._registry = registry
        self._cache = cache
        self._ttl_calc = ttl_calc

    async def get_kline(
        self, code: str, period: str, count: int, market: str = "a_stock"
    ) -> list[Kline]:
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

        bucket = self._ttl_calc.bucket_for(
            "kline_daily" if period in ("1d", "1w", "1M") else "kline"
        )
        key = f"kline:{code}:{period}:{bucket}"
        cached = await self._cache.get(key)
        if cached:
            import json

            data = json.loads(cached)
            return [Kline.model_validate(item) for item in data]

        klines = await self._registry.fan_out_in_sublist(
            sub, "get_kline", code=code, period=period, count=count
        )
        ttl = self._ttl_calc.ttl_seconds("kline_daily" if period in ("1d", "1w", "1M") else "kline")
        import json

        await self._cache.set(key, json.dumps([k.model_dump(mode="json") for k in klines]), ttl=ttl)
        return klines
