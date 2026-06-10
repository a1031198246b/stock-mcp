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

## 编码规范

- 公共方法必须有类型注解
- 异常使用 `domain/errors.py` 中的类
- 缓存键格式: `{data_type}:{key}:{bucket}`
- 所有 async 方法
- 测试用 TDD 模式
