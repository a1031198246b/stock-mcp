"""行情服务 - 编排缓存 + 多源 fallback"""
import time
from typing import List, Optional, Dict
from ..domain.models import Quote
from ..adapters.registry import AdapterRegistry


class InMemoryQuoteCache:
    """P1 阶段占位 - P2 替换为 SQLite"""

    def __init__(self, ttl_seconds: int = 3):
        self._store: Dict[str, tuple] = {}  # key -> (quote, expire_at)
        self._ttl = ttl_seconds

    def _key(self, code: str) -> str:
        return f"quote:{code}"

    def get(self, code: str) -> Optional[Quote]:
        item = self._store.get(self._key(code))
        if not item:
            return None
        quote, expire_at = item
        if time.time() > expire_at:
            return None
        return quote

    def set(self, quote: Quote) -> None:
        self._store[self._key(quote.code)] = (quote, time.time() + self._ttl)

    def clear(self) -> None:
        self._store.clear()


class QuoteService:
    def __init__(self, registry: AdapterRegistry, cache: InMemoryQuoteCache):
        self._registry = registry
        self._cache = cache

    async def get_realtime_quote(self, codes: List[str]) -> List[Quote]:
        # 1. 尝试缓存
        cached = []
        missing = []
        for code in codes:
            q = self._cache.get(code)
            if q:
                cached.append(q)
            else:
                missing.append(code)

        if not missing:
            return cached

        # 2. 缓存未命中, 走 registry
        fresh = await self._registry.fan_out("get_realtime_quote", codes=missing)

        # 3. 写缓存
        for q in fresh:
            self._cache.set(q)

        return cached + fresh
