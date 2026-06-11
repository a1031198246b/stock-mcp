# Changelog

## 2026-06-11

### 修复
- **K线 DataFrame 解析** (`tqcenter.py:get_kline`): 字段名大写 (`Open`/`High`/`Low`/`Close`/`Volume`/`Amount`), 时间戳在 DataFrame `index` 而非 `time` 字段. 旧实现按平行数组 + 小写字段写, 永远返回空.
- **get_fundamental DLL 异常处理**: 不存在代码 (如 999999) 触发 tqcenter 抛 "代码格式错误", 改为捕获并返回 `None` (优雅降级).

### 新增
- **tqcenter 基本面真实数据** (`tqcenter.py:get_fundamental`): 用 `get_stock_info` + 实时价计算 PE/PB/ROE/市值/行业代码. 替代 P1 stub (`return None`).
- **新增 6 个单元测试** + **2 个集成测试** 覆盖基本面.
- **文档更新**:
  - README: 状态更新, P3 标记完成, 加"已知限制"章节
  - DATA_SOURCES: tqcenter 覆盖范围更新, 加 PE 偏差和锁状态警告
- **GitHub Actions CI** (`.github/workflows/ci.yml`): 3 个 job, lint (ruff) + test (pytest + 覆盖率 ≥ 90%, 3.11/3.12 矩阵) + typecheck (mypy, 渐进式 continue-on-error). 集成测试通过 TDX_PATH="" 自动 skip.
- **ruff 配置** (`pyproject.toml`): `[tool.ruff]` + `[tool.ruff.format]`, 全项目已格式化.
- **mypy 配置** (`pyproject.toml`): `[tool.mypy]` strict 模式, 当前非阻塞, 修完错误后升级.

### 测试
- 139 passed, 16 skipped, 91% 总体覆盖率 (CI 验证)
- 18 个 tqcenter 单元测试全过
- 10 个 tdxcenter 集成测试全过 (需 TDX 重启后)
- TDX 端运行时验证: 茅台 PE 14.64 / PB 5.9 / ROE 10.06% / 市值 15957.29 亿

## 2026-06-12

### 新增
- **baostock 适配器** (`baostock_source.py`): A 股 K线 (深度历史) + 财务三表 (income/balance/cashflow)
- **yfinance 适配器** (`yfinance_source.py`): 港股 (00700.HK) + 美股 (AAPL) 行情/K线/基本面
- **多市场支持**: 5 个现有工具加 `market` 参数 ("a_stock" / "hk" / "us"), 默认 "a_stock" (向后兼容)
- **get_financial_statement 工具**: 暴露 baostock 财务三表
- **Market Literal type** + 所有 4 个 domain model 加 `market` 字段
- **新依赖**: `baostock>=0.8.9` + `yfinance>=0.2.40`

### 改动
- BaseAdapter 加 `supported_markets: list[str]` 字段 (默认 ["a_stock"])
- AdapterRegistry 加 `fan_out_in_sublist` 方法 (按 market 子集 fallback)
- 4 个 service 加 market 路由, service→adapter 也透传 market=market

## 2026-06-10 之前

- P0-P4 阶段完成
- 5 适配器全部实现 (tqcenter / sina / akshare / eastmoney / iwencai)
- 缓存 / 限流 / 熔断器 / 多源 fallback 完整
- 集成测试 fixture 已支持 TDX 重试 3 次
