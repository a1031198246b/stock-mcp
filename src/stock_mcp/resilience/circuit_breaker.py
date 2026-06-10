"""熔断器 - CLOSED → OPEN → HALF_OPEN → CLOSED"""
import asyncio
import time
from enum import Enum
from typing import Awaitable, Callable, TypeVar

from ..domain.errors import DataSourceError

T = TypeVar("T")


class CircuitState(str, Enum):
    CLOSED = "closed"
    OPEN = "open"
    HALF_OPEN = "half_open"


class CircuitOpenError(DataSourceError):
    def __init__(self, name: str):
        super().__init__(f"circuit open for {name}", source=name)


class CircuitBreaker:
    def __init__(self, name: str = "default", failure_threshold: int = 3, recovery_timeout: int = 300):
        self.name = name
        self._failure_threshold = failure_threshold
        self._recovery_timeout = recovery_timeout
        self._state = CircuitState.CLOSED
        self._failure_count = 0
        self._opened_at: float | None = None

    @property
    def state(self) -> CircuitState:
        if self._state == CircuitState.OPEN and self._opened_at is not None:
            if time.time() - self._opened_at >= self._recovery_timeout:
                self._state = CircuitState.HALF_OPEN
        return self._state

    async def call(self, func: Callable[[], Awaitable[T] | T]) -> T:
        if self.state == CircuitState.OPEN:
            raise CircuitOpenError(self.name)

        try:
            ret = func()
            if asyncio.iscoroutine(ret) or isinstance(ret, asyncio.Future):
                result = await ret
            else:
                result = ret  # type: ignore[assignment]
        except Exception as e:
            await self.record_failure()
            raise

        await self.record_success()
        return result

    async def record_failure(self) -> None:
        self._failure_count += 1
        if self._failure_count >= self._failure_threshold:
            self._state = CircuitState.OPEN
            self._opened_at = time.time()

    async def record_success(self) -> None:
        self._failure_count = 0
        self._state = CircuitState.CLOSED
        self._opened_at = None
