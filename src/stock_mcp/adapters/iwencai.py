"""爱问财（iWencai）适配器 - 自然语言选股、回测

依赖: pywencai (需 Node.js 16+)

Cookie 是可选的: 未配置时 pywencai 以匿名模式运行, 数据可能不完整
但仍可使用 (例如 ``今日涨停``、``市值<100亿`` 都能返回结果).
"""

from typing import Any

import pandas as pd

from ..config import get_settings
from ..domain.errors import AuthError, DataSourceError
from ..domain.models import (
    Fundamental,
    Kline,
    Market,
    NewsItem,
    Quote,
    StockQueryResult,
)
from .base import BaseAdapter


class IwencaiAdapter(BaseAdapter):
    name = "iwencai"
    priority = 0  # 自然语言查询专用, 不参与行情 fallback
    enabled = False  # 默认禁用, 满足条件才启用

    def __init__(self) -> None:
        self._pywencai: Any | None = None

    def initialize(self) -> None:
        try:
            import pywencai  # type: ignore[import-not-found]
        except ImportError:
            return
        self._pywencai = pywencai
        self.enabled = True

    async def get_realtime_quote(self, codes: list[str], market: Market = "a_stock") -> list[Quote]:
        raise NotImplementedError

    async def get_kline(
        self, code: str, period: str, count: int, market: Market = "a_stock"
    ) -> list[Kline]:
        raise NotImplementedError

    async def get_fundamental(self, code: str, market: Market = "a_stock") -> Fundamental | None:
        raise NotImplementedError

    async def get_news(self, code: str, limit: int, market: Market = "a_stock") -> list[NewsItem]:
        raise NotImplementedError

    async def query_stocks(self, condition: str) -> list[StockQueryResult]:
        if not self.enabled:
            raise DataSourceError("iwencai 未启用 (pywencai 未安装)", source=self.name)
        settings = get_settings()
        # 把空串 (常见于 .env 里留 ``IWENCAI_COOKIE=``) 也视为未配置
        cookie = settings.iwencai_cookie or None
        try:
            pywc = self._pywencai
            assert pywc is not None
            df = pywc.get(
                question=condition,
                cookie=cookie,
                loop=True,  # 自动翻页
            )
        except Exception as e:
            msg = str(e)
            # 仅当 cookie 已配置且 pywencai 提示登录/cookie 相关错误时,
            # 才视为认证问题. 匿名模式下出现的错误归类为数据源错误.
            if cookie and ("登录" in msg or "cookie" in msg.lower() or "expired" in msg.lower()):
                raise AuthError(msg, source=self.name) from e
            raise DataSourceError(msg, source=self.name) from e

        results: list[StockQueryResult] = []
        if df is None or df.empty:
            return results

        # 列名映射 (pywencai 默认返回中文列名)
        code_col = next((c for c in df.columns if "代码" in c or "code" in c.lower()), None)
        name_col = next((c for c in df.columns if "名称" in c or "name" in c.lower()), None)

        if not code_col:
            return results

        for _, row in df.iterrows():
            code = str(row[code_col]).zfill(6)
            name = str(row[name_col]) if name_col else ""
            # 其它字段作为 matched_fields
            matched = {
                col: (None if pd.isna(v) else v)
                for col, v in row.items()
                if col not in (code_col, name_col)
            }
            results.append(
                StockQueryResult(
                    code=code,
                    name=name,
                    matched_fields=matched,
                )
            )
        return results
