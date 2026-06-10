"""通达信 tqcenter 适配器

依赖: 本机安装通达信客户端 + tqcenter 插件（默认在 TDX_PATH/PYPlugins/user/）
如不可用, 适配器自动 disabled
"""
import sys
from pathlib import Path
from typing import List, Optional
import pandas as pd
from ..config import get_settings
from ..domain.models import Quote, Kline, Fundamental, NewsItem
from ..domain.errors import DataSourceError, NotFoundError
from .base import BaseAdapter


class TqcenterAdapter(BaseAdapter):
    name = "tqcenter"
    priority = 1  # 最高优先级
    enabled = False  # 默认禁用, 初始化成功才启用

    def __init__(self):
        self._tq = None
        self._initialized = False
        self._stock_info_cache: dict = {}

    def initialize(self) -> None:
        """同步初始化 - 必须在异步方法调用前完成"""
        if self._initialized:
            return

        settings = get_settings()
        tdx_path = settings.tdx_path
        if not tdx_path:
            return  # TDX_PATH 未配置, 保持 disabled

        # 添加 tqcenter 路径
        tq_path = Path(tdx_path) / "PYPlugins" / "user"
        if tq_path.exists():
            sys.path.insert(0, str(tq_path))
        try:
            import tqcenter
        except Exception:
            return

        self._tq = tqcenter.tq
        try:
            self._tq.close()  # 释放可能残留的连接
        except Exception:
            pass

        # 尝试多种 run_mode
        for mode in range(10):
            try:
                self._tq.run_mode = mode
                self._tq._initialized = False
                self._tq.initialize(tdx_path)
                self._initialized = True
                self.enabled = True
                return
            except Exception:
                continue

    async def health_check(self) -> bool:
        if not self._initialized or not self.enabled:
            return False
        try:
            stocks = self._tq.get_stock_list("5")
            return bool(stocks)
        except Exception:
            self.enabled = False
            return False

    async def get_realtime_quote(self, codes: List[str]) -> List[Quote]:
        if not self._initialized:
            raise DataSourceError("tqcenter 未初始化", source=self.name)

        results = []
        for code in codes:
            try:
                snap = self._tq.get_market_snapshot(code)
                if not snap or float(snap.get("Now", 0)) <= 0:
                    raise NotFoundError(f"无法获取 {code} 行情")
                info = self._stock_info_cache.get(code) or self._safe_stock_info(code)
                now = float(snap.get("Now", 0))
                last_close = float(snap.get("LastClose", 0))
                change_pct = ((now - last_close) / last_close * 100) if last_close > 0 else 0
                results.append(Quote(
                    code=code.split(".")[0],
                    name=info.get("Name", ""),
                    price=round(now, 2),
                    change_pct=round(change_pct, 2),
                    amount=float(snap.get("Amount", 0)),
                    volume=int(float(snap.get("Volume", 0))),
                    open=float(snap.get("Open", 0)),
                    high=float(snap.get("Max", 0)),
                    low=float(snap.get("Min", 0)),
                    last_close=last_close,
                    bid_5=self._safe_int_list(snap.get("Buyv", []), 5),
                    ask_5=self._safe_int_list(snap.get("Sellv", []), 5),
                    timestamp=pd.Timestamp.now().to_pydatetime(),
                    source=self.name,
                ))
            except NotFoundError:
                raise
            except Exception as e:
                raise DataSourceError(str(e), source=self.name)
        return results

    # 周期映射: tqcenter 协议 → 分钟数
    _PERIOD_MAP = {
        "1m": 1, "5m": 5, "15m": 15, "30m": 30, "60m": 60,
        "1h": 60, "1d": 0, "1w": -1, "1M": -2,
    }

    async def get_kline(self, code: str, period: str, count: int) -> List[Kline]:
        if not self._initialized:
            raise DataSourceError("tqcenter 未初始化", source=self.name)
        if period not in self._PERIOD_MAP:
            raise DataSourceError(f"不支持的 period: {period}", source=self.name)

        try:
            category = self._PERIOD_MAP[period]
            # get_security_bars 返回 numpy 结构
            result = self._tq.get_security_bars(category, 0, code, 0, count)
            if result is None or len(result) == 0:
                return []
            # result 字段: datetime, open, high, low, close, amount, volume
            klines = []
            for bar in result:
                # datetime 可能是 int (yyyyMMddHHmm) 或 pandas Timestamp
                dt = bar['datetime']
                if isinstance(dt, (int, float)) and dt > 1e10:
                    # yyyyMMddHHmm 格式
                    import datetime as _dt
                    year = int(dt // 100000000)
                    month = int((dt // 1000000) % 100)
                    day = int((dt // 10000) % 100)
                    hour = int((dt // 100) % 100)
                    minute = int(dt % 100)
                    dt_obj = _dt.datetime(year, month, day, hour, minute)
                else:
                    dt_obj = pd.Timestamp(dt).to_pydatetime()
                klines.append(Kline(
                    code=code.split(".")[0],
                    period=period,
                    datetime=dt_obj,
                    open=float(bar['open']),
                    high=float(bar['high']),
                    low=float(bar['low']),
                    close=float(bar['close']),
                    volume=int(bar['vol']),
                    amount=float(bar['amount']),
                    source=self.name,
                ))
            return klines
        except DataSourceError:
            raise
        except Exception as e:
            raise DataSourceError(str(e), source=self.name)

    async def get_fundamental(self, code: str) -> Optional[Fundamental]:
        """P1 阶段先返回 None"""
        return None

    async def get_news(self, code: str, limit: int) -> List[NewsItem]:
        """P1 阶段先返回空"""
        return []

    def _safe_stock_info(self, code: str) -> dict:
        try:
            info = self._tq.get_stock_info(code)
            if info and info.get("ErrorId") == "0":
                self._stock_info_cache[code] = info
                return info
        except Exception:
            pass
        return {}

    @staticmethod
    def _safe_int_list(v, n: int) -> List[int]:
        out = []
        for i in range(n):
            try:
                out.append(int(float(v[i])) if i < len(v) and v[i] else 0)
            except Exception:
                out.append(0)
        return out
