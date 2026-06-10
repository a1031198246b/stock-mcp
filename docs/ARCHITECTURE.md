# 架构

A 股股票数据 MCP 服务的系统架构。

## 分层

```
┌──────────────────────────────────────────────────────────┐
│              Claude Code (MCP Client)                    │
└────────────────────────┬─────────────────────────────────┘
                         │ stdio (JSON-RPC 2.0)
┌────────────────────────▼─────────────────────────────────┐
│                MCP Server (FastMCP)                      │
│  Tools 层    - get_realtime_quote / get_kline / ...      │
│  Service 层  - 缓存 + 熔断 + 限流 + 多源 fallback 编排   │
│  Adapter 层  - 5 个数据源适配器 (统一 BaseAdapter 接口)  │
│  基础设施    - 缓存 / 日志 / 配置 / 限流 / 熔断           │
└──────────────────────────────────────────────────────────┘
```

## 核心原则

- **依赖倒置**: Service 只依赖 Adapter 接口, 不知道具体数据源
- **可插拔**: 加新数据源 = 加一个 adapter 类
- **可降级**: 主源失败 → 自动 fallback → 缓存兜底
- **可观测**: 所有请求有 trace_id, 所有源调用有 latency

## 模块职责

| 层 | 职责 | 文件 |
|---|---|---|
| `domain/` | 数据模型 + 异常体系 (零依赖) | `models.py`, `errors.py` |
| `adapters/` | 数据源适配器, 统一 BaseAdapter 接口 | `base.py`, 5 个具体源 |
| `services/` | 业务编排 (缓存 + fallback) | `quote_service.py`, `kline_service.py`, ... |
| `cache/` | SQLite + TTL 策略 | `sqlite_cache.py`, `ttl.py` |
| `ratelimit/` | 令牌桶限流 | `token_bucket.py` |
| `resilience/` | 熔断器 | `circuit_breaker.py` |
| `tools/` | MCP 工具注册 | `quote.py`, `kline.py`, ... |
| `server.py` | FastMCP 入口 | - |
| `config.py` | 全局配置 (环境变量) | - |
| `logging_setup.py` | structlog 初始化 | - |
