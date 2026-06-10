# Stock MCP

A 股股票数据 MCP 服务。详见 `E:\claude codeworkspace\docs\superpowers\specs\2026-06-10-stock-mcp-design.md`。

## 状态

- [x] **P0 脚手架** — 项目结构、配置、日志、MCP server
- [x] **P1 核心数据** — tqcenter 实时行情 + K 线
- [ ] **P2 多源 + 韧性** — sina/akshare 适配器、缓存、熔断、限流
- [ ] **P3 扩展数据** — 基本面、资讯、eastmoney
- [ ] **P4 高级查询** — iwencai 自然语言选股
- [ ] **P5 完善** — 文档、CI、覆盖率

## 安装

```bash
uv sync --all-extras
cp .env.example .env
# 编辑 .env 设置 TDX_PATH（通达信安装路径）
```

## 运行

```bash
uv run stock-mcp
```

## 测试

```bash
uv run pytest
uv run pytest --cov=stock_mcp
```

## 接入 Claude Code

在 Claude Code 的 `settings.json` 中：

```json
{
  "mcpServers": {
    "stock-mcp": {
      "command": "uv",
      "args": ["--directory", "E:/claude codeworkspace/stock-mcp", "run", "stock-mcp"]
    }
  }
}
```

## 已实现 MCP 工具

| 工具 | 说明 |
|---|---|
| `ping` | 健康检查 |
| `get_realtime_quote` | 实时行情 |
| `get_kline` | K线数据 |
