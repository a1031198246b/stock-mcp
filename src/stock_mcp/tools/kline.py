"""K线 MCP 工具"""

from fastmcp import FastMCP

from ..domain.errors import DataSourceError
from ..services.kline_service import KlineService


def register(mcp: FastMCP, service: KlineService) -> None:

    @mcp.tool()
    async def get_kline(code: str, period: str = "1d", count: int = 30) -> str:
        """获取 K 线数据

        Args:
            code: 股票代码，如 "600519"
            period: K线周期，可选 1m/5m/15m/30m/1h/1d/1w/1M
            count: 数量，默认 30
        Returns:
            Markdown 表格
        """
        try:
            klines = await service.get_kline(code, period, count)
        except DataSourceError as e:
            return f"❌ K线获取失败: {e}"

        if not klines:
            return f"❌ {code} 无 K线数据"

        lines = [
            f"**{code} {period} K线（共 {len(klines)} 条）**",
            "",
            "| 日期 | 开 | 高 | 低 | 收 | 成交量(手) | 成交额(亿) |",
            "|------|----|----|----|----|-----------|-----------|",
        ]
        for k in klines:
            lines.append(
                f"| {k.datetime.strftime('%Y-%m-%d %H:%M')} | {k.open} | "
                f"{k.high} | {k.low} | {k.close} | {k.volume} | {k.amount / 1e8:.2f} |"
            )
        return "\n".join(lines)
