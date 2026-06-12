"""TTL 单测 (2026-06-12 简化后)

realtime_quote/kline_minute/news TTL 已被砍, 只测 kline_daily + fundamental.
"""

from stock_mcp.cache.ttl import TTLCalculator, TTLConfig


def test_default_ttl():
    """默认 TTL: 日线 1 天 + 基本面 1 天"""
    cfg = TTLConfig()
    assert cfg.kline_daily == 86400
    assert cfg.fundamental == 86400


def test_ttl_calculator_uses_daily_bucket():
    """日线桶: 同一 1 天内共用, 跨天分开"""
    calc = TTLCalculator(TTLConfig())
    t1 = calc.bucket_for("kline_daily", base_time=1000.0)
    t2 = calc.bucket_for("kline_daily", base_time=1000.0)
    assert t1 == t2
    # 跨 1 天
    t3 = calc.bucket_for("kline_daily", base_time=1000.0 + 86401)
    assert t1 != t3


def test_ttl_default_for_unknown_type():
    """未知 data_type 兜底 1 天 (86400)"""
    calc = TTLCalculator(TTLConfig())
    assert calc.ttl_seconds("unknown_type") == 86400
