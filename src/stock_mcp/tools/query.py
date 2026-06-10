"""查询类 MCP 工具 - 自然语言选股、回测"""
from fastmcp import FastMCP
from ..services.query_service import QueryService
from ..domain.errors import DataSourceError, AuthError


def register(mcp: FastMCP, service: QueryService) -> None:

    @mcp.tool()
    async def query_stocks(condition: str) -> str:
        """自然语言选股（爱问财）

        Args:
            condition: 自然语言条件, 如 "今日涨停 且 市值<100亿"
        Returns:
            Markdown 表格
        """
        try:
            results = await service.query_stocks(condition)
        except AuthError as e:
            return f"❌ iwencai 认证失败: {e}\n请更新 .env 中 IWENCAI_COOKIE 并重启服务"
        except DataSourceError as e:
            return f"❌ 查询失败: {e}"

        if not results:
            return f"❌ 未找到符合条件的股票"

        lines = [
            f"**查询条件: {condition}**",
            f"**共 {len(results)} 条结果**",
            "",
            "| 代码 | 名称 | 命中字段 |",
            "|------|------|---------|",
        ]
        for r in results[:100]:  # 限制 100 条
            matched_str = ", ".join(
                f"{k}={v}" for k, v in list(r.matched_fields.items())[:3]
            )
            lines.append(f"| {r.code} | {r.name} | {matched_str} |")
        return "\n".join(lines)
