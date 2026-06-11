"""管理类工具：健康检查、缓存管理"""

from fastmcp import FastMCP


def register(mcp: FastMCP) -> None:
    @mcp.tool()
    async def ping() -> dict:
        """检查 MCP 服务是否存活（无依赖，可用于链路验证）"""
        return {"status": "ok", "service": "stock-mcp"}
