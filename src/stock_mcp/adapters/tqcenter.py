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

    @staticmethod
    def _to_tq_code(code: str) -> str:
        """补全 tqcenter 要求的 "6位代码.市场后缀" 格式

        输入: "600519" / "600519.SH" / "sh600519"
        输出: "600519.SH"
        """
        c = code.strip().upper()
        # 已经有 .SH/.SZ/.BJ 后缀
        if "." in c:
            return c
        # 去掉可能的前缀 sh/sz/bj
        for prefix in ("SH", "SZ", "BJ"):
            if c.startswith(prefix) and len(c) == len(prefix) + 6:
                c = c[len(prefix):]
                break
        # 6位代码 -> 加市场后缀
        if len(c) == 6 and c.isdigit():
            # 上海: 6, 9 开头
            if c.startswith(("60", "68", "90")):
                return c + ".SH"
            # 深圳: 0, 3 开头
            if c.startswith(("00", "30")):
                return c + ".SZ"
            # 北京: 4, 8 开头
            if c.startswith(("43", "83", "87")):
                return c + ".BJ"
        # 兜底: 不知道的市场, 原样返回
        return c

    async def get_realtime_quote(self, codes: List[str]) -> List[Quote]:
        if not self._initialized:
            raise DataSourceError("tqcenter 未初始化", source=self.name)

        results = []
        for code in codes:
            tq_code = self._to_tq_code(code)
            try:
                snap = self._tq.get_market_snapshot(tq_code)
                if not snap or float(snap.get("Now", 0)) <= 0:
                    raise NotFoundError(f"无法获取 {code} 行情")
                info = self._stock_info_cache.get(code) or self._safe_stock_info(tq_code)
                now = float(snap.get("Now", 0))
                last_close = float(snap.get("LastClose", 0))
                change_pct = ((now - last_close) / last_close * 100) if last_close > 0 else 0
                results.append(Quote(
                    code=code.split(".")[0],
                    name=info.get("Name", ""),
                    price=round(now, 2),
                    change_pct=round(change_pct, 2),
                    amount=float(snap.get("Amount", 0)) * 10000,  # 万元 -> 元
                    volume=int(float(snap.get("Volume", 0))),     # 已经是手
                    open=float(snap.get("Open", 0)),
                    high=float(snap.get("Max", 0)),
                    low=float(snap.get("Min", 0)),
                    last_close=last_close,
                    bid_5=self._safe_int_list(snap.get("Buyv", []), 5),  # 已经是手
                    ask_5=self._safe_int_list(snap.get("Sellv", []), 5),  # 已经是手
                    timestamp=pd.Timestamp.now().to_pydatetime(),
                    source=self.name,
                ))
            except NotFoundError:
                raise
            except Exception as e:
                raise DataSourceError(str(e), source=self.name)
        return results

    # 周期映射: 我们的 period → tqcenter 合法 period
    _PERIOD_MAP = {
        "1m": "1m",
        "5m": "5m",
        "10m": "10m",
        "15m": "15m",
        "30m": "30m",
        "1h": "1h",
        "1d": "1d",
        "1w": "1w",
        "1M": "1mon",  # 月线
    }

    async def get_kline(self, code: str, period: str, count: int) -> List[Kline]:
        if not self._initialized:
            raise DataSourceError("tqcenter 未初始化", source=self.name)
        if period not in self._PERIOD_MAP:
            raise DataSourceError(f"不支持的 period: {period}", source=self.name)

        try:
            tq_period = self._PERIOD_MAP[period]
            tq_code = self._to_tq_code(code)
            # get_market_data 返回 dict: {'open': [...], 'high': [...], 'low': [...], ...}
            data = self._tq.get_market_data(
                stock_list=[tq_code],
                period=tq_period,
                count=count,
                dividend_type='front',  # 前复权
                fill_data=True,
            )
            if not data or "error" in data:
                return []
            # 解析 dict 成 List[Kline]
            opens = data.get("open", [])
            highs = data.get("high", [])
            lows = data.get("low", [])
            closes = data.get("close", [])
            volumes = data.get("volume", [])
            amounts = data.get("amount", [])
            times = data.get("time", []) or data.get("datetime", [])

            n = min(len(opens), len(highs), len(lows), len(closes))
            klines = []
            import datetime as _dt
            for i in range(n):
                # time 字段是 'YYYYMMDD' 或 'YYYYMMDDHHMM' 字符串
                t_str = str(times[i]) if i < len(times) else ""
                try:
                    if len(t_str) >= 14:
                        dt_obj = _dt.datetime(
                            int(t_str[0:4]), int(t_str[4:6]), int(t_str[6:8]),
                            int(t_str[8:10]) if len(t_str) >= 10 else 0,
                            int(t_str[10:12]) if len(t_str) >= 12 else 0,
                        )
                    elif len(t_str) >= 8:
                        dt_obj = _dt.datetime(int(t_str[0:4]), int(t_str[4:6]), int(t_str[6:8]))
                    else:
                        dt_obj = pd.Timestamp.now().to_pydatetime()
                except Exception:
                    dt_obj = pd.Timestamp.now().to_pydatetime()

                klines.append(Kline(
                    code=code.split(".")[0],
                    period=period,
                    datetime=dt_obj,
                    open=float(opens[i]),
                    high=float(highs[i]),
                    low=float(lows[i]),
                    close=float(closes[i]),
                    volume=int(float(volumes[i])) if i < len(volumes) else 0,
                    amount=float(amounts[i]) if i < len(amounts) else 0.0,
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
