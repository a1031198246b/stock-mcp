"""通达信 tqcenter 适配器

依赖: 本机安装通达信客户端 + tqcenter 插件（默认在 TDX_PATH/PYPlugins/user/）
如不可用, 适配器自动 disabled
"""

import sys
from pathlib import Path

import pandas as pd

from ..config import get_settings
from ..domain.errors import DataSourceError, NotFoundError
from ..domain.models import Fundamental, Kline, NewsItem, Quote
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

        # 尝试多种 run_mode
        # 关键: 每次重试前, 调用 close() (它会调 dll.CloseConnect 真正释放锁)
        # 之前直接 self._tq._initialized = False 是个 bug - 只骗了 Python 没骗 DLL,
        # 下次 init 时 DLL 报"已有同名策略运行"
        for mode in range(10):
            try:
                # 释放可能的残留锁
                try:
                    self._tq.close()
                except Exception:
                    pass
                # 给 DLL 一点时间真正释放
                import time as _time

                _time.sleep(0.2)

                self._tq.run_mode = mode
                # 不再手动设 self._tq._initialized = False
                # 让 _auto_initialize 自己管理
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
                c = c[len(prefix) :]
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

    async def get_realtime_quote(self, codes: list[str], market: str = "a_stock") -> list[Quote]:
        if not self._initialized:
            raise DataSourceError("tqcenter 未初始化", source=self.name)

        results = []
        for code in codes:
            tq_code = self._to_tq_code(code)
            try:
                snap = self._tq.get_market_snapshot(tq_code)
                # 非交易时段 / 通达信刚启动数据未就绪: snapshot 返回但 Now=0
                # 不抛错, 而是跳过这只股票 (让 registry fallback 到下个源)
                if not snap or float(snap.get("Now", 0)) <= 0:
                    continue  # 优雅降级, 不抛 NotFoundError
                info = self._stock_info_cache.get(code) or self._safe_stock_info(tq_code)
                now = float(snap.get("Now", 0))
                last_close = float(snap.get("LastClose", 0))
                change_pct = ((now - last_close) / last_close * 100) if last_close > 0 else 0
                results.append(
                    Quote(
                        code=code.split(".")[0],
                        name=info.get("Name", ""),
                        price=round(now, 2),
                        change_pct=round(change_pct, 2),
                        amount=float(snap.get("Amount", 0)) * 10000,  # 万元 -> 元
                        volume=int(float(snap.get("Volume", 0))),  # 已经是手
                        open=float(snap.get("Open", 0)),
                        high=float(snap.get("Max", 0)),
                        low=float(snap.get("Min", 0)),
                        last_close=last_close,
                        bid_5=self._safe_int_list(snap.get("Buyv", []), 5),  # 已经是手
                        ask_5=self._safe_int_list(snap.get("Sellv", []), 5),  # 已经是手
                        timestamp=pd.Timestamp.now().to_pydatetime(),
                        source=self.name,
                    )
                )
            except NotFoundError:
                raise
            except Exception as e:
                raise DataSourceError(str(e), source=self.name) from e
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

    async def get_kline(
        self, code: str, period: str, count: int, market: str = "a_stock"
    ) -> list[Kline]:
        if not self._initialized:
            raise DataSourceError("tqcenter 未初始化", source=self.name)
        if period not in self._PERIOD_MAP:
            raise DataSourceError(f"不支持的 period: {period}", source=self.name)

        try:
            tq_period = self._PERIOD_MAP[period]
            tq_code = self._to_tq_code(code)
            # tqcenter.get_market_data 返回 dict: {'Open': Series, 'High': Series, ...}
            # 注意: 字段名是 **大写** (Open/High/Low/Close/Volume/Amount),
            #       时间戳在 **DataFrame 的 index** 里, 不是字段
            data = self._tq.get_market_data(
                stock_list=[tq_code],
                period=tq_period,
                count=count,
                dividend_type="front",  # 前复权
                fill_data=True,
            )
            if not data or "error" in data:
                return []

            # 兼容大小写: tqcenter 返回大写, 但防御性兼容小写
            def _col(d, *names):
                for n in names:
                    if n in d and len(d[n]) > 0:
                        return d[n]
                return None

            opens_df = _col(data, "Open", "open")
            highs_df = _col(data, "High", "high")
            lows_df = _col(data, "Low", "low")
            closes_df = _col(data, "Close", "close")
            volumes_df = _col(data, "Volume", "volume")
            amounts_df = _col(data, "Amount", "amount")
            if opens_df is None or closes_df is None:
                return []  # 没拉到核心字段, 当作空数据

            # tqcenter 把每只股票作为 DataFrame 的一个 column
            # 例如 data['Open'] 是 DataFrame, columns=['600519.SH'], index=DatetimeIndex
            # 抽出我们要的这只股票的 Series
            def _series_for_code(df):
                if tq_code in df.columns:
                    return df[tq_code]
                # 兜底: 取第一列
                return df.iloc[:, 0]

            opens = _series_for_code(opens_df)
            highs = _series_for_code(highs_df)
            lows = _series_for_code(lows_df)
            closes = _series_for_code(closes_df)
            volumes = _series_for_code(volumes_df) if volumes_df is not None else None
            amounts = _series_for_code(amounts_df) if amounts_df is not None else None

            n = min(len(opens), len(highs), len(lows), len(closes))
            klines = []
            for i in range(n):
                # 时间从 Series 的 DatetimeIndex 拿
                try:
                    dt_obj = pd.Timestamp(opens.index[i]).to_pydatetime()
                except Exception:
                    dt_obj = pd.Timestamp.now().to_pydatetime()

                def _scalar(series, idx, default=0):
                    if series is None or idx >= len(series):
                        return default
                    try:
                        return float(series.iloc[idx])
                    except Exception:
                        return default

                klines.append(
                    Kline(
                        code=code.split(".")[0],
                        period=period,
                        datetime=dt_obj,
                        open=_scalar(opens, i),
                        high=_scalar(highs, i),
                        low=_scalar(lows, i),
                        close=_scalar(closes, i),
                        volume=int(_scalar(volumes, i)),
                        amount=_scalar(amounts, i, 0.0),
                        source=self.name,
                    )
                )
            return klines
        except DataSourceError:
            raise
        except Exception as e:
            raise DataSourceError(str(e), source=self.name) from e

    async def get_fundamental(self, code: str, market: str = "a_stock") -> Fundamental | None:
        """从 tqcenter.get_stock_info + 实时价 拼出基本面

        tqcenter 本身不直接提供 PE/PB, 但提供:
        - J_zgb (总股本, 万股), J_mgsy (每股收益, 元), J_mgjzc (每股净资产, 元)
        - J_jzc (净资产), J_zzc (总资产), J_jly (净利润)
        - J_hy (行业代码)
        配合实时价, 我们自己算 PE / PB / 市值
        """
        if not self._initialized:
            raise DataSourceError("tqcenter 未初始化", source=self.name)
        tq_code = self._to_tq_code(code)
        try:
            info = self._tq.get_stock_info(tq_code)
        except Exception:
            # tqcenter 对不存在/格式不对的代码会抛 "股票代码格式错误" 异常
            # (Bug 1 修复后 _to_tq_code 已补后缀, 但 DLL 内部仍校验代码在股票列表中)
            # 上层 (get_realtime_quote) 用 NotFoundError 表示, 这里直接 None
            return None

        if not info or info.get("ErrorId") != "0":
            return None

        # tqcenter 字段名是大写; 全部可能是字符串, 用 _f 安全转 float
        def _f(d, key, default=0.0):
            v = d.get(key, default)
            try:
                return float(v)
            except (TypeError, ValueError):
                return default

        # 拿实时价算 PE/PB
        try:
            snap = self._tq.get_market_snapshot(tq_code)
            price = float(snap.get("Now", 0)) if snap else 0.0
        except Exception:
            price = 0.0

        # 单位换算:
        # - J_zgb 是"万股", 我们的 model 要"亿股", 所以 / 10000
        # - 我们的 model 市值单位"亿元", = price * 总股本(股) / 1e8
        #   = price * J_zgb(万股) * 10000 / 1e8
        #   = price * J_zgb / 10000
        total_shares_wan = _f(info, "J_zgb")  # 万股
        total_shares_yi = total_shares_wan / 10000.0  # 亿股 (model 字段)
        market_cap = price * total_shares_wan / 10000.0  # 亿元 (model 字段)
        # 注意: 万 * 元 / 10000 = 亿元, 这里写 price * J_zgb / 10000

        eps = _f(info, "J_mgsy")  # 元/股
        bps = _f(info, "J_mgjzc")  # 元/股
        pe = price / eps if eps > 0 else 0.0  # 用最新季报 EPS 算 (注: 不是 TTM)
        pb = price / bps if bps > 0 else 0.0

        # ROE 近似: 净利润 / 净资产
        jly = _f(info, "J_jly")  # 净利润, 元
        jzc = _f(info, "J_jzc")  # 净资产, 元
        roe = (jly / jzc) if jzc > 0 else 0.0

        # 行业代码: tqcenter 给的是 TDX 内部数字, 名称映射是 TDX 私有表
        # 为避免错映射, 这里只回传原始代码 (字符串), 上层可查公开 TDX 行业表
        hy_code = info.get("J_hy", 0)
        try:
            industry = str(int(hy_code))
        except (TypeError, ValueError):
            industry = None

        return Fundamental(
            code=code.split(".")[0],
            name=info.get("Name", ""),
            pe=round(pe, 2) if pe > 0 else None,
            pb=round(pb, 2) if pb > 0 else None,
            roe=round(roe, 4) if roe > 0 else None,  # ROE 是小数 (0.15 = 15%)
            total_shares=round(total_shares_yi, 4) if total_shares_yi > 0 else None,
            market_cap=round(market_cap, 2) if market_cap > 0 else None,
            industry=industry,
            source=self.name,
        )

    # 注意: industry 字段当前是 TDX 内部行业代码 (字符串数字).
    # 完整的 TDX 行业代码 → 中文名 映射表是 TDX 私有数据 (~100+ 项),
    # 硬编码容易错 (我之前编的 45 个有近一半错). 上层 (UI / iwencai / akshare) 拿到后
    # 可查公开的证监会行业分类做转换. 这里只保证 raw code 正确.

    async def get_news(self, code: str, limit: int, market: str = "a_stock") -> list[NewsItem]:
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
    def _safe_int_list(v, n: int) -> list[int]:
        out = []
        for i in range(n):
            try:
                out.append(int(float(v[i])) if i < len(v) and v[i] else 0)
            except Exception:
                out.append(0)
        return out
