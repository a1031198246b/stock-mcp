"""资讯 MCP 工具"""

from fastmcp import FastMCP

from ..domain.errors import DataSourceError
from ..services.news_service import NewsService


def register(mcp: FastMCP, service: NewsService) -> None:
    @mcp.tool()
    async def get_news(code: str, limit: int = 20) -> str:
        """获取股票资讯和公告

        Args:
            code: 股票代码
            limit: 数量，默认 20
        Returns:
            Markdown 列表
        """
        try:
            items = await service.get_news(code, limit=limit)
        except DataSourceError as e:
            return f"❌ 资讯获取失败: {e}"

        if not items:
            return f"❌ {code} 暂无资讯"

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
