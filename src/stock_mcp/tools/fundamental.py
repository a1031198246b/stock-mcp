"""基本面 MCP 工具"""

from fastmcp import FastMCP

from ..domain.errors import DataSourceError
from ..services.fundamental_service import FundamentalService


def register(mcp: FastMCP, service: FundamentalService) -> None:
    @mcp.tool()
    async def get_fundamental(code: str) -> str:
        """获取个股基本面数据

        Args:
            code: 股票代码
        Returns:
            Markdown 格式
        """
        try:
            fund = await service.get_fundamental(code)
        except DataSourceError as e:
            return f"❌ 基本面获取失败: {e}"
        if fund is None:
            return f"❌ 未找到 {code} 基本面数据"

        return (
            f"**{fund.code} {fund.name} 基本面数据**\n"
            f"- 市盈率(PE): {fund.pe or 'N/A'}\n"
            f"- 市净率(PB): {fund.pb or 'N/A'}\n"
            f"- 净资产收益率(ROE): {fund.roe or 'N/A'}\n"
            f"- 总股本: {fund.total_shares or 'N/A'} 亿股\n"
            f"- 总市值: {fund.market_cap or 'N/A'} 亿元\n"
            f"- 行业: {fund.industry or 'N/A'}\n"
            f"- 数据源: {fund.source}\n"
        )
