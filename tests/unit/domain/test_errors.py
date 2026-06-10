from stock_mcp.domain.errors import (
    StockMCPError,
    DataSourceError,
    RateLimitError,
    AuthError,
    ParseError,
    NotFoundError,
    CacheError,
)


def test_stock_mcp_error_is_base():
    assert issubclass(DataSourceError, StockMCPError)


def test_data_source_error_carries_source():
    err = DataSourceError("timeout", source="tqcenter")
    assert err.source == "tqcenter"
    assert "timeout" in str(err)


def test_rate_limit_error_has_retry_after():
    err = RateLimitError("429", source="sina", retry_after=60)
    assert err.retry_after == 60
    assert err.source == "sina"


def test_auth_error_defaults_to_iwencai():
    err = AuthError("cookie expired")
    assert err.source == "iwencai"


def test_parse_error_inherits_data_source():
    err = ParseError("bad json", source="akshare")
    assert isinstance(err, DataSourceError)
    assert err.source == "akshare"


def test_not_found_error_is_not_data_source():
    err = NotFoundError("code 999999")
    assert not isinstance(err, DataSourceError)
    assert isinstance(err, StockMCPError)


def test_cache_error_is_not_fatal_subclass():
    err = CacheError("disk full")
    assert isinstance(err, StockMCPError)
    # CacheError 故意不继承 DataSourceError
    assert not isinstance(err, DataSourceError)
