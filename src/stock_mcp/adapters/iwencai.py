"""爱问财（iWencai）适配器 - 自然语言选股、回测

依赖: pywencai (需 Node.js 16+)
"""

import pandas as pd

from ..config import get_settings
from ..domain.errors import AuthError, DataSourceError
from ..domain.models import (
    StockQueryResult,
)
from .base import BaseAdapter


class IwencaiAdapter(BaseAdapter):
    name = "iwencai"
    priority = 0  # 自然语言查询专用, 不参与行情 fallback
    enabled = False  # 默认禁用, 满足条件才启用

    def __init__(self):
        self._pywencai = None

    def initialize(self) -> None:
        settings = get_settings()
        if not settings.iwencai_cookie:
            return
        try:
            import pywencai
        except ImportError:
            return
        self._pywencai = pywencai
        self.enabled = True

    async def get_realtime_quote(self, codes):
        raise NotImplementedError

    async def get_kline(self, code, period, count):
        raise NotImplementedError

    async def get_fundamental(self, code):
        raise NotImplementedError

    async def get_news(self, code, limit):
        raise NotImplementedError

    async def query_stocks(self, condition: str) -> list[StockQueryResult]:
        if not self.enabled:
            raise DataSourceError(
                "iwencai 未启用 (cookie 缺失或 pywencai 未安装)", source=self.name
            )
        settings = get_settings()
        try:
            df = self._pywencai.get(
                question=condition,
                cookie=settings.iwencai_cookie,
                loop=True,  # 自动翻页
            )
        except Exception as e:
            msg = str(e)
            if "登录" in msg or "cookie" in msg.lower() or "expired" in msg.lower():
                raise AuthError(msg, source=self.name) from e
            raise DataSourceError(msg, source=self.name) from e

        results = []
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
