"""令牌桶限流器"""

import asyncio
import time


class TokenBucket:
    def __init__(self, capacity: int, refill_rate: float):
        """capacity: 桶容量; refill_rate: 每秒补充的令牌数"""
        self._capacity = capacity
        self._refill_rate = refill_rate
        self._tokens = float(capacity)
        self._last_refill = time.monotonic()
        self._lock = asyncio.Lock()

    def _refill(self) -> None:
        now = time.monotonic()
        elapsed = now - self._last_refill
        self._tokens = min(
            self._capacity,
            self._tokens + elapsed * self._refill_rate,
        )
        self._last_refill = now

    async def acquire(self, timeout: float | None = None) -> bool:
        async with self._lock:
            self._refill()
            if self._tokens >= 1:
                self._tokens -= 1
                return True
            if timeout is None or timeout <= 0:
                return False
            # 等待
            wait_time = (1 - self._tokens) / self._refill_rate
            if wait_time > timeout:
                return False
            await asyncio.sleep(wait_time)
            self._refill()
            if self._tokens >= 1:
                self._tokens -= 1
                return True
            return False
