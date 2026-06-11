# Stock MCP

A 股股票数据 MCP 服务。详见 `E:\claude codeworkspace\docs\superpowers\specs\2026-06-10-stock-mcp-design.md`。

## 状态

- [x] **P0 脚手架** — 项目结构、配置、日志、MCP server
- [x] **P1 核心数据** — tqcenter 实时行情 + K 线
- [x] **P2 多源 + 韧性** — sina/akshare 适配器、缓存、熔断、限流
- [x] **P3 扩展数据** — tqcenter 基本面（PE/PB/ROE/市值）+ 资讯 + eastmoney
- [x] **P4 高级查询** — iwencai 自然语言选股
- [ ] **P5 完善** — 文档、CI、覆盖率（当前 89%）

## 安装

```bash
uv sync --all-extras
cp .env.example .env
# 编辑 .env 设置 TDX_PATH（通达信安装路径）
# 可选: 设置 IWENCAI_COOKIE 启用自然语言选股
```

## 运行

```bash
uv run stock-mcp
```

## 测试

```bash
# 单元测试 (mock 适配器, 无外部依赖)
uv run pytest

# 覆盖率
uv run pytest --cov=stock_mcp

# 集成测试 (需本地通达信 + TDX_PATH)
TDX_PATH="C:\new_tdx64" uv run pytest tests/integration/tdxcenter/ -v
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

| 工具 | 说明 | 数据源 |
|---|---|---|
| `ping` | 健康检查 | — |
| `get_realtime_quote` | 实时行情（含5档买卖盘） | tqcenter / sina / akshare |
| `get_kline` | K线（1m/5m/15m/30m/1h/1d/1w/1M） | tqcenter / sina |
| `get_fundamental` | 基本面（PE/PB/ROE/市值/行业代码） | tqcenter |
| `get_news` | 资讯公告 | eastmoney / akshare |
| `query_stocks` | 自然语言选股（需 iwencai cookie） | iwencai |

## 数据源能力矩阵

| 适配器 | 实时行情 | K线 | 基本面 | 资讯 | 选股 |
|---|---|---|---|---|---|
| **tqcenter** (主) | ✅ 含5档 | ✅ 1d/1w/1M/分钟 | ✅ PE/PB/ROE/市值 | ❌ | ❌ |
| **sina** (备) | ✅ | ⚠️ 部分 | ❌ | ❌ | ❌ |
| **akshare** | ✅ | ✅ | ✅ | ✅ | ❌ |
| **eastmoney** | ❌ | ⚠️ 补全 | ❌ | ✅ | ❌ |
| **iwencai** (可选) | ❌ | ❌ | ❌ | ❌ | ✅ |

## 已实现 MCP 工具

| 工具 | 说明 |
|---|---|
| `ping` | 健康检查 |
| `get_realtime_quote` | 实时行情 |
| `get_kline` | K线数据 |
| `get_fundamental` | 基本面数据 |
| `get_news` | 资讯公告 |
| `query_stocks` | 自然语言选股（需 iwencai cookie） |

## 数据源

- **tqcenter** (priority 1, 主源)：通达信插件，需本地安装
- **sina** (priority 2)：新浪财经 HTTP
- **akshare** (priority 3)：开源金融数据库
- **eastmoney** (priority 4)：东方财富，资讯公告
- **iwencai** (可选)：自然语言选股，需 cookie + Node.js

## 已知限制

- **tqcenter 基本面** 的 `industry` 字段是 **TDX 内部行业代码**（字符串数字，如 `"37"` 表示白酒）。完整的 TDX 行业代码 → 中文名映射是 TDX 私有数据，硬编码容易出错。需要中文行业名时，可查公开的证监会行业分类或 akshare 的 stock_individual_info_em 自行转换。
- **tqcenter PE** 是基于**最新季报 EPS** 算的（不是 TTM），财报发布后会有偏差。需要在交易时间内拉数据。
- **tqcenter 锁状态**：TDX 端 PYMP 服务有连接槽位限制。如果反复失败会让 TDX 卡死，需要手动重启 tdxw.exe 解锁。`tests/integration/tdxcenter/test_real.py` 的 fixture 内部已 3 次重试，**不要**在 adapter 里再加循环避免锁状态污染。
- **5档买卖盘** 中买一/卖一以外的盘口在非交易活跃时段常常为 0，这是真实数据（流动性低），不是 bug。
