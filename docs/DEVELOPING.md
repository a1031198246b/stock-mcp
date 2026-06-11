# 开发指南

## 开发环境

- Python 3.11+
- uv (包管理)
- 通达信客户端 (可选, 用于 tqcenter 集成测试)
- Node.js 16+ (可选, 用于 iwencai)

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
2. 实现 5 个核心方法: `get_realtime_quote`, `get_kline`, `get_fundamental`, `get_news`, `query_stocks`
3. 在 `src/stock_mcp/server.py` 的 `create_server()` 中注册
4. 添加单元测试 (用 `respx` mock HTTP, 或 `unittest.mock` mock 模块)

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
2. 实现 4 个核心方法: `get_realtime_quote`, `get_kline`, `get_fundamental`, `get_news`
3. 在 `src/stock_mcp/server.py` 的 `create_server()` 中注册
4. 添加单元测试 (用 `respx` mock HTTP, 或 `unittest.mock` mock 模块)
5. 如果是真实数据源, 加集成测试 (用 `TDX_PATH` 跳过机制)

### tqcenter 适配器要点

tqcenter 库返回结构 (重要, 跟其他源不同):

- **行情** (`get_market_snapshot`): 普通 dict, `Now`/`LastClose`/`Amount`/`Volume`/`Open`/`Max`/`Min`/`Buyv`/`Sellv`
- **K线** (`get_market_data`): dict, **每个值是 DataFrame** (column=股票代码, index=DatetimeIndex). 字段名**大写** `Open`/`High`/`Low`/`Close`/`Volume`/`Amount`, 时间在 `index` 里, 没有 `time` 字段.
- **基本面** (`get_stock_info`): 普通 dict, 字段 `J_zgb`(总股本, 万股)/`J_mgsy`(EPS)/`J_mgjzc`(每股净资产)/`J_jzc`(净资产)/`J_jly`(净利润)/`J_hy`(行业代码, TDX 内部数字).
- **代码格式**: tqcenter 严格要求 `6位代码.市场后缀` (如 `600519.SH`), 我们的 `_to_tq_code` 自动补后缀.
- **行业代码**: tqcenter 的 `J_hy` 是 TDX 内部数字, 不要硬编码猜测中文名. 上层可查公开的证监会行业分类做转换.

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
