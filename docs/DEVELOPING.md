# 开发指南

## 开发环境

- Python 3.11+
- uv (包管理)
- 通达信客户端 (可选, 用于 tqcenter 集成测试)
- Node.js 16+ (可选, 用于 iwencai; cookie 可选, 无 cookie 用匿名模式)

## 本地开发

```bash
# 克隆代码
cd E:/claude codeworkspace/stock-mcp

# 安装依赖
uv sync --all-extras

# 跑测试
uv run pytest

# 跑覆盖率
uv run pytest --cov=stock_mcp

# 启动服务
uv run stock-mcp
```

## 添加新数据源

1. 继承 `BaseAdapter` (位于 `src/stock_mcp/adapters/base.py`)
2. **设置类属性** `name`, `priority`, `supported_markets: list[str]` (默认 ["a_stock"])
3. 实现 5 个核心方法: `get_realtime_quote`, `get_kline`, `get_fundamental`, `get_news`, `query_stocks` — **每个都接 `market: str = "a_stock"` 参数**
4. (可选) 实现 `get_financial_statement` 方法暴露**财务三表** (目前仅 baostock 实现, 给 A 股用)
5. 在 `src/stock_mcp/server.py` 的 `create_server()` 中注册
6. 添加单元测试 (用 `respx` mock HTTP, 或 `unittest.mock` mock 模块)

示例:
```python
class MyAdapter(BaseAdapter):
    name = "my_source"
    priority = 10
    enabled = True

    async def get_realtime_quote(self, codes): ...
    async def get_kline(self, code, period, count): ...
    async def get_fundamental(self, code): ...
    async def get_news(self, code, limit): ...
```

## 添加新 MCP 工具

1. 在 `src/stock_mcp/tools/` 新建 `xxx.py`
2. 定义 `register(mcp, service)` 函数, 用 `@mcp.tool()` 装饰
3. 在 `src/stock_mcp/tools/__init__.py` 的 `register_all_tools()` 中注册
4. 添加单元测试

## 添加新数据源 / 扩展适配器能力

1. 继承 `BaseAdapter` (位于 `src/stock_mcp/adapters/base.py`)
2. **设置类属性** `name`, `priority`, `supported_markets: list[str]`
3. 实现 5 个核心方法: `get_realtime_quote`, `get_kline`, `get_fundamental`, `get_news`, `get_query_stocks` — **每个都接 `market: str = "a_stock"` 参数**
4. 在 `src/stock_mcp/server.py` 的 `create_server()` 中注册
5. 添加单元测试 (用 `respx` mock HTTP, 或 `unittest.mock` mock 模块)

### 当前 8 个适配器 (priority 数字小优先)

| 适配器 | priority | supported_markets | 覆盖 |
|---|---|---|---|
| tqcenter | 1 | a_stock | 行情 + K线 + 基本面 |
| eastmoney | 2 | a_stock, hk, us | A 股资讯 + 港美股实时/K线 (字段稳, 优先) |
| baostock | 3 | a_stock | K线 + 财务三表 |
| akshare | 4 | a_stock | 行情 + K线 + 基本面 + 资讯 |
| sina | 5 | a_stock, hk, us | A 股 32 字段含五档 (A 股首选), 港美股实时兜底 |
| tencent | 6 | a_stock, hk, us | A 股实时 + 港美股 K线 |
| yfinance | 7 | hk, us | 海外 fallback (国内被限) |
| iwencai | 0 | a_stock | 自然语言选股 (独立, 不参与 fallback) |

### priority 设计原则 (2026-06-12)

**港美股路由**: `eastmoney(2) → sina(5) → yfinance(7)`
- eastmoney 优先: 单股 secid 查询, 字段 `f43/f44/f45/f46/f60/f170` 固定, **不会盘前盘后错位**
- sina 兜底: 同端, 32/18/30 字段盘中 OK, 盘前盘后字段错位 (sina 上游限制)
- yfinance 兜底: 国内被限 (push2delay 403), 仅海外/住宅代理可用

**A 股路由**:
- 行情: `tqcenter(1) → sina(5) [32 字段五档] → tencent(6) → eastmoney(2)` (eastmoney A 股返回 [], 实际 sina 兜底)
- K线: `tqcenter(1) → baostock(3) → akshare(4) → tencent(6) → eastmoney(2)` (eastmoney A 股 K线返回 [])
- 资讯: `eastmoney(2) → akshare(4)` (eastmoney 优先, 因为 ann_type=A 端稳)
- 财务: `baostock(3)` (唯一源)

### tqcenter 适配器要点

tqcenter 库返回结构 (重要, 跟其他源不同):

- **行情** (`get_market_snapshot`): 普通 dict, `Now`/`LastClose`/`Amount`/`Volume`/`Open`/`Max`/`Min`/`Buyv`/`Sellv`
- **K线** (`get_market_data`): dict, **每个值是 DataFrame** (column=股票代码, index=DatetimeIndex). 字段名**大写** `Open`/`High`/`Low`/`Close`/`Volume`/`Amount`, 时间在 `index` 里, 没有 `time` 字段.
- **基本面** (`get_stock_info`): 普通 dict, 字段 `J_zgb`(总股本, 万股)/`J_mgsy`(EPS)/`J_mgjzc`(每股净资产)/`J_jzc`(净资产)/`J_jly`(净利润)/`J_hy`(行业代码, TDX 内部数字).
- **代码格式**: tqcenter 严格要求 `6位代码.市场后缀` (如 `600519.SH`), 我们的 `_to_tq_code` 自动补后缀.
- **行业代码**: tqcenter 的 `J_hy` 是 TDX 内部数字, 不要硬编码猜测中文名. 上层可查公开的证监会行业分类做转换.

## Linting and Type Checking

The project uses ruff and mypy, configured in `pyproject.toml`.

**Before committing**, run:

```bash
# Lint (matches CI lint job)
uv run ruff check .

# Format check (matches CI lint job)
uv run ruff format --check .

# Auto-fix lint and format
uv run ruff check . --fix
uv run ruff format .

# Type check (matches CI typecheck job, currently non-blocking)
uv run mypy src/stock_mcp
```

**CI will block** the merge if:
- `ruff check` or `ruff format --check` fails
- `pytest --cov-fail-under=90` fails (coverage below 90%)

**CI will NOT block** for:
- `mypy` errors (continue-on-error, plan is to fix incrementally)

## 编码规范

- 公共方法必须有类型注解
- 异常使用 `domain/errors.py` 中的类
- 缓存键格式: `{data_type}:{key}:{bucket}`
- 所有 async 方法
- 测试用 TDD 模式

## ⚠️ TDX 端锁状态保护

tqcenter 库通过 RPC 跟 TDX 进程 (`tdxw.exe`) 通信. TDX 端有有限数量的 Python 策略槽位.
- **不要**在 adapter 里对 10 个 run_mode 硬循环, 这会快速耗尽 TDX 端槽位, 让 `InitConnect` 一直返回 "Connect ERROR" (ErrorId 11).
- **不要**在测试 fixture 里也硬循环, 同样会卡死 TDX.
- 当前 `tests/integration/tdxcenter/test_real.py` 的 `tq_adapter` fixture 已用 3 次重试 + 1 秒 sleep, 这是合理上限.
- 如果 TDX 端卡死 (所有 mode 都 ErrorId 11), 需要手动重启 `tdxw.exe` 解锁. 重启后 `run_id` 会重置.
