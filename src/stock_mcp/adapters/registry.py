"""适配器注册表 - 负责优先级排序、fan-out fallback"""

from typing import Any

from ..domain.errors import DataSourceError
from .base import BaseAdapter


class AdapterRegistry:
    def __init__(self, adapters: list[BaseAdapter]):
        self._adapters = list(adapters)
        self._unhealthy: dict[str, float] = {}  # name -> 恢复时间戳

    def adapters_in_order(self) -> list[BaseAdapter]:
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

    async def fan_out(self, method_name: str, *args: Any, **kwargs: Any) -> Any:
        """按优先级依次调用方法，全部失败抛 DataSourceError"""
        errors: list[tuple[str, Exception | str]] = []
        for adapter in self.adapters_in_order():
            if self.is_unhealthy(adapter.name):
                continue
            method = getattr(adapter, method_name)
            try:
                result = await method(*args, **kwargs)
            except Exception as e:
                errors.append((adapter.name, e))
                # 连续失败不直接熔断, 让 Service 层处理
                continue

            # 调用成功, 但要区分"真无数据" vs "没实现"
            # 列表类型: 空列表 = 真无数据, 应继续 fallback
            # None/其他 falsy: 视为真无数据
            if isinstance(result, list) and len(result) == 0:
                errors.append((adapter.name, "empty result"))
                continue
            if result is None:
                errors.append((adapter.name, "None result"))
                continue

            # 有数据, 返回
            self.mark_healthy(adapter.name)
            return result

        # 全部失败
        if errors:
            sources = [n for n, _ in errors]
            raise DataSourceError(
                f"所有适配器失败: {', '.join(sources)}",
                source=sources[0] if sources else "unknown",
            )
        raise DataSourceError("无可用适配器", source="registry")

    async def fan_out_in_sublist(
        self, adapters: list[BaseAdapter], method_name: str, *args: Any, **kwargs: Any
    ) -> Any:
        """在指定适配器子集内按优先级 fallback (跳过 unhealthy)

        与 fan_out 的区别: 只在传入的子集内尝试, 不查 registry 全集.
        用于 service 层做 market 路由: 只在支持当前 market 的适配器里选.
        """
        errors: list[tuple[str, Exception | str]] = []
        for adapter in sorted(adapters, key=lambda a: a.priority):
            if self.is_unhealthy(adapter.name):
                continue
            method = getattr(adapter, method_name)
            try:
                result = await method(*args, **kwargs)
            except Exception as e:
                errors.append((adapter.name, e))
                continue

            if isinstance(result, list) and len(result) == 0:
                errors.append((adapter.name, "empty result"))
                continue
            if result is None:
                errors.append((adapter.name, "None result"))
                continue

            self.mark_healthy(adapter.name)
            return result

        if errors:
            sources = [n for n, _ in errors]
            raise DataSourceError(
                f"子集适配器失败: {', '.join(sources)}",
                source=sources[0] if sources else "unknown",
            )
        raise DataSourceError("无可用适配器", source="registry")
