from stock_mcp.cache.ttl import TTLCalculator, TTLConfig


def test_default_ttl_for_realtime_quote():
    cfg = TTLConfig()
    assert cfg.realtime_quote == 3
    assert cfg.kline_daily == 86400
    assert cfg.kline_minute == 60
    assert cfg.fundamental == 86400
    assert cfg.news == 600


def test_ttl_calculator_uses_bucket_for_realtime():
    """实时行情用桶策略（同一 3 秒内共用）"""
    calc = TTLCalculator(TTLConfig())
    t1 = calc.bucket_for("realtime_quote", base_time=1000.0)
    t2 = calc.bucket_for("realtime_quote", base_time=1001.0)
    t3 = calc.bucket_for("realtime_quote", base_time=1003.5)
    assert t1 == t2  # 同一桶
    assert t1 != t3  # 跨桶
