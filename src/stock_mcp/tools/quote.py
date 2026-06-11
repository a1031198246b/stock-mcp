"""行情类 MCP 工具"""

from fastmcp import FastMCP

from ..domain.errors import DataSourceError
from ..services.quote_service import QuoteService


def register(mcp: FastMCP, service: QuoteService) -> None:

    @mcp.tool()
    async def get_realtime_quote(codes: list[str], market: str = "a_stock") -> str:
        """获取股票实时行情

        Args:
            codes: 股票代码列表，如 ["600519"] (A 股) / ["00700"] (港股) / ["AAPL"] (美股)
            market: 市场, "a_stock" (默认) / "hk" / "us"
        Returns:
            Markdown 表格，包含代码、名称、价格、涨跌幅、成交额
        """
        try:
            quotes = await service.get_realtime_quote(codes, market=market)
        except DataSourceError as e:
            return f"❌ 数据获取失败: {e}\n请检查网络或稍后重试"

        # Markdown 表格
        lines = [
            "| 代码 | 名称 | 价格 | 涨跌幅(%) | 成交额(亿) | 成交量(手) | 买一量 | 卖一量 | 数据源 |",
            "|------|------|------|-----------|-----------|-----------|--------|--------|--------|",
        ]
        for q in quotes:
            lines.append(
                f"| {q.code} | {q.name} | {q.price} | {q.change_pct:+.2f} | "
                f"{q.amount / 1e8:.2f} | {q.volume} | {q.bid_5[0]} | {q.ask_5[0]} | {q.source} |"
            )
        return "\n".join(lines)
