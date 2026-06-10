"""行情类 MCP 工具"""
from typing import List
from fastmcp import FastMCP
from ..services.quote_service import QuoteService
from ..domain.errors import DataSourceError


def register(mcp: FastMCP, service: QuoteService) -> None:

    @mcp.tool()
    async def get_realtime_quote(codes: List[str]) -> str:
        """获取 A 股实时行情

        Args:
            codes: 股票代码列表，如 ["600519", "000001"]
        Returns:
            Markdown 表格，包含代码、名称、价格、涨跌幅、成交额
        """
        try:
            quotes = await service.get_realtime_quote(codes)
        except DataSourceError as e:
            return f"❌ 数据获取失败: {e}\n请检查网络或稍后重试"

        if not quotes:
            return f"❌ 未找到数据: {codes}"

        # Markdown 表格
        lines = [
            "| 代码 | 名称 | 价格 | 涨跌幅(%) | 成交额(亿) | 成交量(手) | 买一量 | 卖一量 | 数据源 |",
            "|------|------|------|-----------|-----------|-----------|--------|--------|--------|",
        ]
        for q in quotes:
            lines.append(
                f"| {q.code} | {q.name} | {q.price} | {q.change_pct:+.2f} | "
                f"{q.amount/1e8:.2f} | {q.volume} | {q.bid_5[0]} | {q.ask_5[0]} | {q.source} |"
            )
        return "\n".join(lines)
