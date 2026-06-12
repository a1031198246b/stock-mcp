"""行情服务 - 不 cache 实时数据

**2026-06-12 简化**: realtime_quote 不 cache. 实时数据频繁变化 (15min 延迟
行情 + 用户调一次就一次), 3s TTL 实际命中率 ~0, 缓存纯浪费.

每次直接调 adapter chain (多源 fallback), 不写盘不查盘.
"""

from typing import cast

from ..adapters.registry import AdapterRegistry
from ..cache.sqlite_cache import SQLiteCache  # 保留依赖, 架构对齐
from ..cache.ttl import TTLCalculator  # 保留依赖, 架构对齐
from ..domain.models import Quote


class QuoteService:
    def __init__(
        self,
        registry: AdapterRegistry,
        cache: SQLiteCache,
        ttl_calc: TTLCalculator,
    ):
        self._registry = registry
        self._cache = cache  # 保留引用, 暂未使用
        self._ttl_calc = ttl_calc  # 保留引用, 暂未使用

    async def get_realtime_quote(self, codes: list[str], market: str = "a_stock") -> list[Quote]:
        # 0. 选 market 子集
        sub = [
            a
            for a in self._registry.adapters_in_order()
            if a.enabled and market in a.supported_markets
        ]
        if not sub:
            raise ValueError(f"market={market} 无可用适配器 (支持: a_stock/hk/us)")

        # 直接调 adapter (多源 fallback), 不 cache
        return cast(
            list[Quote],
            await self._registry.fan_out_in_sublist(
                sub, "get_realtime_quote", codes=codes, market=market
            ),
        )
