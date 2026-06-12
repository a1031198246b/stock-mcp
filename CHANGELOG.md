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

## 2026-06-12

### 修复
- **eastmoney 港美股实时** (`eastmoney.py:get_realtime_quote`): 改用单股 secid 查询 (`/api/qt/stock/get?secid=116.00700`) 替代 clist 全市场拉取 (push2delay 302 重定向后 pz 最大 100, 腾讯 00700 排序靠后被截). 字段 f60 启发式: f60 >= 100000 用 ÷1000 (港股 3 位小数), 否则 ÷100 (美股 2 位).
- **eastmoney 302 redirect**: `_get_with_retry` 加 `follow_redirects=True` (push2 → push2delay).
- **sina 美股字段**: 用 sina 给的 change_pct (fields[2]) 不自己算, 避免盘前字段错位.

### 调整
- **adapter priority 重新分配** (2026-06-12):
  - tqcenter: 1 (不变)
  - eastmoney: 4 → **2** (港美股字段稳, 优先 sina)
  - baostock: 2 → 3
  - akshare: 3 → 4
  - sina: 2 → **5** (A 股 32 字段五档实时首选, 港美股实时兜底)
  - tencent: 5 → 6
  - yfinance: 5 → 7 (国内被限, 明确海外 fallback)
  - iwencai: 0 (不变, 独立)
- 新路由:
  - 港美股实时: eastmoney(2) → sina(5) → yfinance(7)
  - A 股实时: tqcenter(1) → sina(5) [五档] → tencent(6) (eastmoney A 股返回 [])
  - A 股 K线: tqcenter(1) → baostock(3) → akshare(4) → tencent(6) (eastmoney A 股 K线返回 [])

### 新增
- **4 个 service 层单测** (`test_routing_priority.py`): 验证 priority 排序生效
  - 港美股实时 → eastmoney 优先
  - A 股实时 → sina 优先 (五档)
  - eastmoney 失败 fallback sina
  - 真实 adapter priority 字段符合设计

### 文档
- **DEVELOPING.md**: 适配器表从 7 个扩展到 8 个, 加 priority 设计原则章节
- **DATA_SOURCES.md**: 全部重写, 反映 8 适配器 + 新 priority 路由

### 测试
- 227 passed, 29 skipped, 90% 覆盖率 (CI gate 过)
- 集成测: `RUN_EASTMONEY_TESTS=1` 4/4 PASS (港美股实时 + K线, 之前默认 skip)
