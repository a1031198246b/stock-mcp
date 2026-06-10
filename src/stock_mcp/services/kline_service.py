"""K线服务"""
import time
from typing import List, Dict, Optional
from ..domain.models import Kline
from ..adapters.registry import AdapterRegistry


class InMemoryKlineCache:
    def __init__(self, ttl_seconds: int = 60):
        self._store: Dict[str, tuple] = {}
        self._ttl = ttl_seconds

    def _key(self, code: str, period: str) -> str:
        return f"kline:{code}:{period}"

    def get(self, code: str, period: str) -> Optional[List[Kline]]:
        item = self._store.get(self._key(code, period))
        if not item or time.time() > item[1]:
            return None
        return item[0]

    def set(self, code: str, period: str, klines: List[Kline]) -> None:
        self._store[self._key(code, period)] = (klines, time.time() + self._ttl)

    def clear(self):
        self._store.clear()


class KlineService:
    def __init__(self, registry: AdapterRegistry, cache: InMemoryKlineCache):
        self._registry = registry
        self._cache = cache

    async def get_kline(self, code: str, period: str, count: int) -> List[Kline]:
        cached = self._cache.get(code, period)
        if cached and len(cached) >= count:
            return cached[:count]

        klines = await self._registry.fan_out("get_kline", code=code, period=period, count=count)
        self._cache.set(code, period, klines)
        return klines
