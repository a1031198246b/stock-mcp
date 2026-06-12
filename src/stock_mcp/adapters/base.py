"""适配器抽象基类"""

from abc import ABC, abstractmethod
from collections.abc import Callable, Coroutine
from functools import wraps
from typing import Any

from ..domain.models import Fundamental, Kline, Market, NewsItem, Quote, StockQueryResult


class BaseAdapter(ABC):
    """所有数据源适配器必须实现此接口"""

    name: str = "abstract"
    priority: int = 100  # 数字越小越优先
    enabled: bool = True
    supported_markets: list[str] = ["a_stock"]  # 默认仅 A 股

    async def health_check(self) -> bool:
        """默认实现：始终健康。子类可重写做真实检查。"""
        return True

    @abstractmethod
    async def get_realtime_quote(self, codes: list[str], market: Market = "a_stock") -> list[Quote]:
        """获取实时行情"""
        raise NotImplementedError

    @abstractmethod
    async def get_kline(
        self, code: str, period: str, count: int, market: Market = "a_stock"
    ) -> list[Kline]:
        """获取 K 线，period ∈ {1m, 5m, 15m, 30m, 1h, 1d, 1w, 1M}"""
        raise NotImplementedError

    @abstractmethod
    async def get_fundamental(self, code: str, market: Market = "a_stock") -> Fundamental | None:
        """获取个股基本面"""
        raise NotImplementedError

    @abstractmethod
    async def get_news(self, code: str, limit: int, market: Market = "a_stock") -> list[NewsItem]:
        """获取资讯公告"""
        raise NotImplementedError

    async def query_stocks(self, condition: str) -> list[StockQueryResult]:
        """自然语言选股 - 默认不支持（仅 iwencai 重写）"""
        raise NotImplementedError(f"{self.name} 不支持自然语言选股")

    def __init_subclass__(cls, **kwargs: Any) -> None:
        """子类化时自动包装返回 Quote/Kline/Fundamental 的方法，注入 source 字段"""
        super().__init_subclass__(**kwargs)

        if cls.get_realtime_quote is not BaseAdapter.get_realtime_quote:
            _orig_quote: Callable[..., Coroutine[Any, Any, list[Quote]]] = cls.get_realtime_quote

            @wraps(_orig_quote)
            async def wrapped_get_realtime_quote(
                self: "BaseAdapter", codes: list[str], *args: Any, **kw: Any
            ) -> list[Quote]:
                quotes = await _orig_quote(self, codes, *args, **kw)
                for q in quotes:
                    q.source = self.name
                return quotes

            cls.get_realtime_quote = wrapped_get_realtime_quote  # type: ignore[method-assign]

        if cls.get_kline is not BaseAdapter.get_kline:
            _orig_kline: Callable[..., Coroutine[Any, Any, list[Kline]]] = cls.get_kline

            @wraps(_orig_kline)
            async def wrapped_get_kline(
                self: "BaseAdapter", code: str, period: str, count: int, *args: Any, **kw: Any
            ) -> list[Kline]:
                klines = await _orig_kline(self, code, period, count, *args, **kw)
                for k in klines:
                    k.source = self.name
                return klines

            cls.get_kline = wrapped_get_kline  # type: ignore[method-assign]

        if cls.get_fundamental is not BaseAdapter.get_fundamental:
            _orig_fund: Callable[..., Coroutine[Any, Any, Fundamental | None]] = cls.get_fundamental

            @wraps(_orig_fund)
            async def wrapped_get_fundamental(
                self: "BaseAdapter", code: str, *args: Any, **kw: Any
            ) -> Fundamental | None:
                fund = await _orig_fund(self, code, *args, **kw)
                if fund is not None:
                    fund.source = self.name
                return fund

            cls.get_fundamental = wrapped_get_fundamental  # type: ignore[method-assign]
