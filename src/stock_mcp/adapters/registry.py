"""适配器注册表 - 负责优先级排序、fan-out fallback"""
from typing import List, Callable, Awaitable, Any
from ..domain.errors import DataSourceError
from .base import BaseAdapter


class AdapterRegistry:
    def __init__(self, adapters: List[BaseAdapter]):
        self._adapters = list(adapters)
        self._unhealthy: dict[str, float] = {}  # name -> 恢复时间戳

    def adapters_in_order(self) -> List[BaseAdapter]:
        """按优先级排序，跳过 disabled / unhealthy"""
        return sorted(
            (a for a in self._adapters if a.enabled and a.name not in self._unhealthy),
            key=lambda a: a.priority,
        )

    def mark_unhealthy(self, name: str, recovery_seconds: int = 300) -> None:
        """标记一个适配器为不健康"""
        import time
        self._unhealthy[name] = time.time() + recovery_seconds

    def mark_healthy(self, name: str) -> None:
        self._unhealthy.pop(name, None)

    def is_unhealthy(self, name: str) -> bool:
        import time
        deadline = self._unhealthy.get(name)
        if deadline is None:
            return False
        if time.time() > deadline:
            self._unhealthy.pop(name)
            return False
        return True

    async def fan_out(self, method_name: str, *args, **kwargs) -> Any:
        """按优先级依次调用方法，全部失败抛 DataSourceError"""
        errors = []
        for adapter in self.adapters_in_order():
            if self.is_unhealthy(adapter.name):
                continue
            method = getattr(adapter, method_name)
            try:
                result = await method(*args, **kwargs)
                self.mark_healthy(adapter.name)
                return result
            except Exception as e:
                errors.append((adapter.name, e))
                # 连续失败不直接熔断, 让 Service 层处理
                continue

        # 全部失败
        if errors:
            sources = [n for n, _ in errors]
            raise DataSourceError(
                f"所有适配器失败: {', '.join(sources)}",
                source=sources[0] if sources else "unknown",
            )
        raise DataSourceError("无可用适配器", source="registry")
