# 数据源说明

## 概览 (8 适配器, 2026-06-12 更新)

| 适配器 | 优先级 | 覆盖 | 强制? | 外部依赖 |
|---|---|---|---|---|
| tqcenter | 1 | A 股实时行情/K线/基本面/5档 | 软强制 | 通达信客户端 |
| eastmoney | 2 | A 股资讯 + 港美股实时/K线 (字段稳, 优先) | 可选 | 无 |
| baostock | 3 | A 股 K线 + 财务三表 | 软强制 | baostock 包 |
| akshare | 4 | A 股基本面/K线/资讯 | 软强制 | akshare 包 |
| sina | 5 | A 股 32 字段含五档实时 + 港美股实时 (兜底) | 软强制 | 无 |
| tencent | 6 | A 股实时 + 港美股 K线 (web.ifzq.gtimg.cn) | 可选 | 无 |
| yfinance | 7 | 港股/美股 (海外 fallback, 国内被限) | 可选 | yfinance 包 + 住宅代理 |
| iwencai | 0 | 自然语言选股 (独立, 不参与 fallback) | 可选 | Node.js; cookie 可选 |

## priority 设计原则

**港美股路由**: `eastmoney(2) → sina(5) → yfinance(7)`
- eastmoney 优先: 单股 secid 查询, 字段固定, 不会盘前盘后错位
- sina 兜底: 港美股字段盘中 OK, 盘前盘后字段错位 (sina 上游限制)
- yfinance 兜底: 国内被限 (push2delay 403/限流), 仅海外/住宅代理可用

**A 股路由**:
- 行情: tqcenter(1) → sina(5) [32 字段五档] → tencent(6) → eastmoney(2) (eastmoney A 股返回 [])
- K线: tqcenter(1) → baostock(3) → akshare(4) → tencent(6) → eastmoney(2) (A 股 K线返回 [])
- 资讯: eastmoney(2) → akshare(4)
- 财务: baostock(3) (唯一源, get_financial_statement 工具)

## 通达信 tqcenter

- **来源**: `C:\new_tdx64\PYPlugins\user\tqcenter`
- **覆盖**: A股实时行情、K线（1d/1w/1M/分钟）、5档、基本面
- **不支持港美股**: tqcenter Python wrapper 不暴露港美股 API, TDX 端有 `dsmarket.dat` HasHKMarket=2 配置但 wrapper 没法调用
- **基本面字段** (从 `get_stock_info` + 实时价计算):
  - 总股本（亿股）、市值（亿元）
  - PE = price / 最新季报 EPS (注意: 不是 TTM)
  - PB = price / 每股净资产
  - ROE = 净利润 / 净资产
  - 行业代码 (TDX 内部数字, 如 `37`=白酒, 需查公开映射表转中文)
- **限频**: 无明确限制
- **稳定性**: 高 (本地进程), 但 TDX 端偶尔卡死 (10 mode 全 ErrorId 11) 需手动重启 tdxw.exe
- **已知问题**:
  - TDX 端 PYMP 服务的 Python 策略槽位有限, 反复 init 失败会卡死
  - 同一进程内对 run_mode 的循环重试要节制, **不要**无脑循环 10 次

## 东方财富 eastmoney (主力港美股源)

- **URL**: `push2.eastmoney.com` (实时单股 secid), `push2his.eastmoney.com` (K线), `np-anotice-stock.eastmoney.com` (A 股资讯)
- **覆盖**:
  - A 股资讯 (`ann_type=A`)
  - 港股实时: `secid=116.{code}` (港股主板)
  - 美股实时: `secid=105.{code}` (NASDAQ)
  - 港美股 K线: 单股 secid
- **稳定性**: 中, 端 502/000 偶发, adapter 内置 3 次重试 + 退避
- **关键实现**:
  - 港美股实时必须用**单股 secid 查询** (push2delay clist API pz 最大 100, 腾讯 00700 排序靠后被截)
  - 字段 f60 (now) ÷1000 (港股 3 位) / ÷100 (美股 2 位) 启发: f60 >= 100000 用 ÷1000
  - `_get_with_retry` 必须 `follow_redirects=True` (push2 → push2delay 302)
- **延迟**: 港美股 15min (跟 yfinance 一样, 数据源都是东方财富)
- **合规风险**: 中
- **集成测**: `RUN_EASTMONEY_TESTS=1 uv run pytest tests/integration/eastmoney/ -v`

## 新浪财经 sina

- **URL**: `hq.sinajs.cn/list={prefix}{code}`
- **覆盖**:
  - A 股: `sh600519` / `sz000001` (32 字段, **含五档买卖**)
  - 港股: `hk00700` (18 字段, 无五档)
  - 美股: `gb_aapl` (~30 字段, 无五档)
- **稳定性**: 高, 国内无需代理
- **限频**: 较松
- **已知问题**:
  - 港美股**盘前/盘后**字段会错位 (跟盘中不同), 解析器用 sina 给的 change_pct 不自己算
  - 美股代码格式特殊: `gb_aapl` 小写, AAPL 转大写
  - K线 JSON API 港美股返回 null, **K线走 eastmoney/tencent**
- **合规风险**: 中

## AKShare

- **安装**: `pip install akshare`
- **覆盖**: A 股基本面、K线、资讯
- **稳定性**: 高 (但 SSL 偶发 EOF, 不在 critical path)
- **合规风险**: 低
- **集成测**: 之前删了 indicators SSL 集成测, 业务上不依赖

## 证券宝 baostock

- **URL**: baostock.com
- **覆盖**: A 股 K线 (深历史) + 财务三表 (利润表/资产负债表/现金流量表)
- **稳定性**: 高 (国内官方)
- **数据准**: baostock 比 akshare 数据准, 适合回溯
- **依赖**: baostock Python 包
- **集成测**: `RUN_BAOSTOCK_TESTS=1 uv run pytest tests/integration/baostock/`
- **不提供**: 实时行情, 资讯, **港美股 (不支持)**
- **已知问题 (修复)**:
  - 财务三表必须带 year/quarter 参数, 不带返回 0 行
  - 0.9.20 + pandas 2.x `DataFrame.append` 已删, `_coerce_df` workaround 用 `rs.data` + `rs.fields` 构造

## 腾讯财经 tencent (K线专项)

- **URL**:
  - 实时 (A 股): `qt.gtimg.cn/q={sh/sz}{code}` (港美股 `v_pv_none_match`, 不通)
  - K线: `web.ifzq.gtimg.cn/appstock/app/fqkline/get?param={code},{period},,,{count},qfq`
- **覆盖**:
  - A 股 实时 (字段 ~28 个, 不含五档)
  - 港美股 K线 (qfqday 或 day 字段, 美股只给 2 行)
- **稳定性**: 高 (同域 web.ifzq.gtimg.cn / qt.gtimg.cn)
- **代码格式特殊** (跟 sina/eastmoney 都不一样):
  - A 股: `sh600519`
  - 港股: `hk00700`
  - 美股: `usAAPL` (us_ 小写 + 代码大写)
- **已知问题**:
  - `content-type` 是 `text/html` 但 body 是 JSON, `_get_with_retry` 自动 JSON/text 切换
  - 港美股 K线 row[6] 是 dict (附加信息), 不是 amount
- **集成测**: `RUN_TENCENT_TESTS=1`

## 雅虎财经 yfinance (海外 fallback)

- **URL**: finance.yahoo.com (通过 yfinance 包)
- **覆盖**: 港股 (0700.HK), 美股 (AAPL), 期货, 外汇
- **稳定性**: **国内被限** (query1.finance.yahoo.com 403/429), 端点全面限流
- **延迟**: 15min
- **合规风险**: 低
- **依赖**: yfinance Python 包
- **HTTP_PROXY**: **需住宅代理**, 普通 datacenter 代理不一定能解
- **不提供**: A 股, 资讯
- **集成测**: `RUN_YFINANCE_TESTS=1`

## 爱问财 iwencai

- **URL**: iwencai.com (通过 pywencai 包)
- **覆盖**: 自然语言选股、回测
- **稳定性**: 中
- **合规风险**: **高** (商业化前需法务评估)
- **依赖**: Node.js 16+, pywencai
- **Cookie**: 可选. 未配置时 pywencai 以匿名模式运行, 部分查询可能受限或返回字段较少, 但常规选股 (如 `今日涨停`、`市值<100亿`) 仍可使用
- **priority=0**: 独立, 不参与其他 adapter 的 fallback chain
