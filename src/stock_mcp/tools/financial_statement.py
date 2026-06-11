"""财务三表 MCP 工具 (仅 baostock 实现)"""

from fastmcp import FastMCP

from ..domain.errors import DataSourceError


def register(mcp: FastMCP, baostock_adapter) -> None:
    """baostock_adapter 是 BaostockAdapter 实例"""

    @mcp.tool()
    async def get_financial_statement(
        code: str,
        statement_type: str = "income",
        market: str = "a_stock",
    ) -> str:
        """获取财务三表 (仅 baostock 数据源)

        Args:
            code: 股票代码 (目前仅 A 股)
            statement_type: "income" (利润表) / "balance" (资产负债表) / "cashflow" (现金流量表)
            market: "a_stock" (默认)
        """
        if baostock_adapter is None or not baostock_adapter.enabled:
            return "❌ 财务数据仅 baostock 适配器支持, 当前不可用 (请检查 baostock 是否安装)"

        try:
            stmt = await baostock_adapter.get_financial_statement(
                code, statement_type, market=market
            )
        except ValueError as e:
            return f"❌ 参数错: {e}"
        except DataSourceError as e:
            return f"❌ baostock 失败: {e}"

        # baostock data 是列向 Dict[col_name, List[values]]
        # 转成行向: List[{col: value}]
        if not stmt.data:
            return f"❌ {code} 无 {statement_type} 数据"

        col_names = list(stmt.data.keys())
        n_rows = max((len(v) for v in stmt.data.values()), default=0)
        if n_rows == 0:
            return f"❌ {code} 无 {statement_type} 数据"

        # 限 8 列避免 Markdown 太宽
        cols = col_names[:8]
        lines = [
            f"**{code} {stmt.name or ''} 财务{_statement_label(statement_type)}**",
            f"**报告期**: {stmt.period}",
            "",
            "| " + " | ".join(cols) + " |",
            "|" + "|".join(["---"] * len(cols)) + "|",
        ]
        for i in range(min(5, n_rows)):  # 限 5 行 (最近 5 期)
            cells = []
            for c in cols:
                vals = stmt.data.get(c, [])
                val = vals[i] if i < len(vals) else ""
                cells.append(str(val)[:30] if val is not None else "")
            lines.append("| " + " | ".join(cells) + " |")
        return "\n".join(lines)


def _statement_label(t: str) -> str:
    return {"income": "利润表", "balance": "资产负债表", "cashflow": "现金流量表"}.get(t, t)
