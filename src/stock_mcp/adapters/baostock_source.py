"""baostock 适配器 - A 股 K线 (深度历史) + 财务三表

baostock 强项: A 股历史数据准, 财务三表全
弱项: 无实时行情, 无资讯
"""

from datetime import datetime
from typing import Any

import pandas as pd

from ..domain.errors import DataSourceError
from ..domain.models import (
    FinancialStatement,
    Fundamental,
    Kline,
    Market,
    NewsItem,
    Quote,
)
from .base import BaseAdapter


def _to_bs_code(code: str) -> str:
    """6位代码 → baostock 格式 (sh.600519 / sz.000001)"""
    code = code.split(".")[0]
    if code.startswith(("60", "68", "11", "13")):
        return f"sh.{code}"
    return f"sz.{code}"


def _coerce_df(result: Any) -> pd.DataFrame:
    """兼容 ResultData (real) 和 DataFrame (mock)

    真实 baostock: rs = bs.query_*(); df = rs.get_data()
    测试 mock: 直接 return_value = pd.DataFrame({...})
    """
    if isinstance(result, pd.DataFrame):
        return result
    # real baostock ResultData
    if hasattr(result, "get_data"):
        df = result.get_data()
        return df if df is not None else pd.DataFrame()
    return pd.DataFrame()


def _check_error(result: Any, op: str, source: str) -> None:
    """如果 result 是 ResultData 且 error_code != '0' 则抛错.

    测试场景下 result 是 DataFrame, 无 error_code 字段, 跳过.
    """
    if hasattr(result, "error_code") and result.error_code != "0":
        msg = getattr(result, "error_msg", "unknown")
        raise DataSourceError(f"baostock {op} 失败: {msg}", source=source)


class BaostockAdapter(BaseAdapter):
    name = "baostock"
    priority = 2  # 同 sina
    enabled = False  # 默认禁用, 初始化成功才启用
    supported_markets = ["a_stock"]

    def __init__(self):
        self._bs = None
        self._logged_in = False

    def initialize(self) -> None:
        try:
            import baostock as bs
        except ImportError:
            return
        self._bs = bs
        self.enabled = True

    def _login(self) -> None:
        """按需登录, 失败抛 DataSourceError"""
        if not self._bs:
            raise DataSourceError("baostock 未初始化", source=self.name)
        if self._logged_in:
            return
        lg = self._bs.login()
        # mock 场景: login 返回 None, 视为成功
        if lg is not None and hasattr(lg, "error_code") and lg.error_code != "0":
            raise DataSourceError(
                f"baostock login 失败: {getattr(lg, 'error_msg', 'unknown')}",
                source=self.name,
            )
        self._logged_in = True

    async def get_realtime_quote(self, codes: list[str], market: Market = "a_stock") -> list[Quote]:
        # baostock 无官方实时接口, 显式抛 (上层 fallback)
        raise DataSourceError("baostock 不支持实时行情, 用 tqcenter 或 sina", source=self.name)

    async def get_kline(
        self, code: str, period: str, count: int, market: Market = "a_stock"
    ) -> list[Kline]:
        self._login()
        # baostock period: d/w/m/5/15/30/60
        period_map = {
            "1d": "d",
            "1w": "w",
            "1M": "m",
            "5m": "5",
            "15m": "15",
            "30m": "30",
            "60m": "60",
        }
        bs_period = period_map.get(period)
        if not bs_period:
            raise DataSourceError(f"baostock 不支持的 period: {period}", source=self.name)

        end_date = datetime.now().strftime("%Y-%m-%d")
        try:
            rs = self._bs.query_history_k_data_plus(
                code=_to_bs_code(code),
                fields="date,open,high,low,close,volume,amount",
                start_date="",
                end_date=end_date,
                frequency=bs_period,
                adjustflag="2",  # 前复权
            )
        except Exception as e:
            raise DataSourceError(str(e), source=self.name) from e

        _check_error(rs, "history_k_data_plus", self.name)
        df = _coerce_df(rs)
        if df is None or df.empty:
            return []
        # 取最后 count 条
        df = df.tail(count)
        klines: list[Kline] = []
        for _, row in df.iterrows():
            klines.append(
                Kline(
                    code=code,
                    period=period,
                    market=market,
                    datetime=pd.Timestamp(row["date"]).to_pydatetime(),
                    open=float(row["open"]),
                    high=float(row["high"]),
                    low=float(row["low"]),
                    close=float(row["close"]),
                    volume=int(float(row["volume"])),
                    amount=float(row["amount"]),
                    source=self.name,
                )
            )
        return klines

    async def get_fundamental(self, code: str, market: Market = "a_stock") -> Fundamental | None:
        # 财务数据走 get_financial_statement, 此方法不重复
        raise NotImplementedError

    async def get_news(self, code: str, limit: int, market: Market = "a_stock") -> list[NewsItem]:
        raise NotImplementedError

    async def get_financial_statement(
        self, code: str, statement_type: str, market: Market = "a_stock"
    ) -> FinancialStatement:
        """baostock 财务三表 — 仅此适配器实现"""
        self._login()
        if statement_type == "income":
            rs = self._bs.query_profit_data(code=_to_bs_code(code))
        elif statement_type == "balance":
            rs = self._bs.query_balance_data(code=_to_bs_code(code))
        elif statement_type == "cashflow":
            rs = self._bs.query_cash_flow_data(code=_to_bs_code(code))
        else:
            raise ValueError(
                f"statement_type 必须是 income/balance/cashflow, 得到 {statement_type}"
            )

        _check_error(rs, statement_type, self.name)
        df = _coerce_df(rs)

        # baostock 第一行含股票名 (例如 "贵州茅台") in 'code_name' column
        name = ""
        if df is not None and not df.empty:
            first_row = df.iloc[0].to_dict()
            for k, v in first_row.items():
                if "code_name" in k or "名称" in k:
                    name = str(v) if v is not None and not pd.isna(v) else ""
                    break

        # data 结构: {col_name: [row_values...]}, 测试断言 data["roeAvg"][0] ≈ 0.10
        data: dict[str, list[Any]] = {}
        period = ""
        if df is not None and not df.empty:
            for col in df.columns:
                col_values: list[Any] = []
                for v in df[col].tolist():
                    if v is None or (isinstance(v, float) and pd.isna(v)):
                        col_values.append(None)
                    else:
                        col_values.append(v)
                data[col] = col_values
            if "statDate" in df.columns and len(df) > 0:
                first_stat = df["statDate"].iloc[0]
                period = (
                    str(first_stat) if first_stat is not None and not pd.isna(first_stat) else ""
                )

        return FinancialStatement(
            code=code,
            name=name,
            market=market,
            period=period,
            statement_type=statement_type,
            data=data,
            source=self.name,
            fetched_at=datetime.now(),
        )
