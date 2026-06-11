"""资讯 MCP 工具"""

from fastmcp import FastMCP

from ..domain.errors import DataSourceError
from ..services.news_service import NewsService


def register(mcp: FastMCP, service: NewsService) -> None:
    @mcp.tool()
    async def get_news(code: str, limit: int = 20, market: str = "a_stock") -> str:
        """获取股票资讯和公告

        Args:
            code: 股票代码，如 "600519" (A 股) / "00700" (港股) / "AAPL" (美股)
            limit: 数量，默认 20
            market: 市场, "a_stock" (默认) / "hk" / "us"
        Returns:
            Markdown 列表
        """
        try:
            items = await service.get_news(code, limit=limit, market=market)
        except DataSourceError as e:
            return f"❌ 资讯获取失败: {e}"

        lines = [
            f"**{code} 资讯公告（共 {len(items)} 条）**",
            "",
            "| 时间 | 标题 | 来源 | 链接 |",
            "|------|------|------|------|",
        ]
        for n in items:
            lines.append(
                f"| {n.publish_time.strftime('%Y-%m-%d %H:%M')} | {n.title} | {n.source} | {n.url} |"
            )
        return "\n".join(lines)
