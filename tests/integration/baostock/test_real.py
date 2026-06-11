"""baostock 真实数据集成测

需要 RUN_BAOSTOCK_TESTS=1 启用, 默认 skip (避免 CI 网络依赖).
实测发现 baostock 财务三表**必须带 year/quarter 参数**, 不带返回 0 行
(这是我们在集成测中验证的产品行为).
"""

import os

import pytest

from stock_mcp.adapters.baostock_source import BaostockAdapter

pytestmark = pytest.mark.skipif(
    os.environ.get("RUN_BAOSTOCK_TESTS") != "1",
    reason="baostock 集成测需 RUN_BAOSTOCK_TESTS=1 (CI 跳过避免网络)",
)


@pytest.mark.asyncio
async def test_real_kline_600519():
    """茅台日 K, 拉 30 天, 验证非空 + 字段齐"""
    a = BaostockAdapter()
    a.initialize()
    assert a.enabled
    klines = await a.get_kline("600519", "1d", 30, market="a_stock")
    assert len(klines) > 0, "baostock K线 空了, 真实拉取失败"
    last = klines[-1]
    assert last.code == "600519"
    assert last.market == "a_stock"
    assert last.close > 0
    assert last.open > 0
    print(f"baostock 600519 最新: {last.datetime.date()} close={last.close} volume={last.volume}")


@pytest.mark.asyncio
async def test_real_kline_000001_shenzhen():
    """深市 000001 (平安银行), 验证 sh/sz 路由"""
    a = BaostockAdapter()
    a.initialize()
    klines = await a.get_kline("000001", "1d", 5, market="a_stock")
    assert len(klines) > 0
    last = klines[-1]
    assert last.code == "000001"
    print(f"baostock 000001 最新: {last.datetime.date()} close={last.close}")


@pytest.mark.asyncio
async def test_financial_statement_needs_year_quarter():
    """**重要产品发现**: baostock 财务三表必须带 year/quarter

    不带参数: error_code=0 但返回 0 行 (空 DataFrame).
    带 year=2025, quarter=4: 返回 1 行, statDate='2025-12-31'.

    **这是当前 adapter 的真实 bug** — 调用永远拿不到数据.
    修复方案: get_financial_statement 应该:
      1. 接受 year/quarter 参数, 或者
      2. 自动拉最近 8 个季度然后合并
    """
    import baostock as bs

    bs.login()
    # 不带参数 → 0 行
    rs_noarg = bs.query_profit_data(code="sh.600519")
    df_noarg = rs_noarg.get_data()
    assert len(df_noarg) == 0, "不带 year/quarter 应返回 0 行 (这是 baostock 行为)"

    # 带参数 → 有数据
    rs_with = bs.query_profit_data(code="sh.600519", year=2025, quarter=4)
    df_with = rs_with.get_data()
    assert len(df_with) == 1, "带 year/quarter 应返回 1 行"
    assert df_with["statDate"].iloc[0] == "2025-12-31"
    print(f"财务三表 2025Q4: roeAvg={df_with['roeAvg'].iloc[0]}")
    bs.logout()


@pytest.mark.asyncio
async def test_get_financial_statement_returns_data_after_fix():
    """修复后: adapter 自动算最近 4 个 quarter, 拿到的 data 非空.

    baostock 季报有 1-2 月延迟, 所以试 5 个 quarter 兜底.
    """
    a = BaostockAdapter()
    a.initialize()
    fs = await a.get_financial_statement("600519", "income", market="a_stock")
    assert fs.code == "600519"
    assert fs.statement_type == "income"
    assert len(fs.data) > 0, f"修复后 data 应非空, 实际 {len(fs.data)} 列"
    assert "statDate" in fs.data, "data 必须含 statDate 列 (报告期)"
    # 应该有 4 行 (4 个季度)
    n_rows = max((len(v) for v in fs.data.values()), default=0)
    assert n_rows >= 1, f"至少 1 行, 实际 {n_rows}"
    print(f"baostock 财务三表: {n_rows} 行, period={fs.period}, cols={len(fs.data)}")
    print(f"  最新 statDate: {fs.data['statDate'][0] if fs.data.get('statDate') else 'N/A'}")
    print(f"  roeAvg: {fs.data.get('roeAvg', ['N/A'])[0]}")
