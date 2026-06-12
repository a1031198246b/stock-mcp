"""K线服务

**2026-06-12 简化**: 只 cache 日线 (1d/1w/1M), 分钟线 (1m/5m/15m/30m/60m) 直接
调 adapter 不 cache. 分钟线数据频繁变化, 缓存命中率低, 不值得占空间.
"""

from typing import cast

from ..adapters.registry import AdapterRegistry
from ..cache.sqlite_cache import SQLiteCache
from ..cache.ttl import TTLCalculator
from ..domain.models import Kline

# 分钟级 period (不 cache), 其余 (1d/1w/1M) cache
_MINUTE_PERIODS = {"1m", "5m", "15m", "30m", "60m"}


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
            raise ValueError(f"market={market} 无可用适配器 (支持: a_stock/hk/us)")

        # 分钟线: 不 cache, 直接调 adapter
        if period in _MINUTE_PERIODS:
            return cast(
                list[Kline],
                await self._registry.fan_out_in_sublist(
                    sub, "get_kline", code=code, period=period, count=count, market=market
                ),
            )

        # 日线/周线/月线: cache 1 天
        bucket = self._ttl_calc.bucket_for("kline_daily")
        key = f"kline:{code}:{period}:{bucket}"
        cached = await self._cache.get(key)
        if cached:
            import json

            data = json.loads(cached)
            return [Kline.model_validate(item) for item in data]

        klines = await self._registry.fan_out_in_sublist(
            sub, "get_kline", code=code, period=period, count=count, market=market
        )
        ttl = self._ttl_calc.ttl_seconds("kline_daily")
        import json

        await self._cache.set(key, json.dumps([k.model_dump(mode="json") for k in klines]), ttl=ttl)
        return cast(list[Kline], klines)
