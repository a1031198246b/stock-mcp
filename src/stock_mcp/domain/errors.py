"""异常体系"""


class StockMCPError(Exception):
    """所有异常的基类"""
    pass


class DataSourceError(StockMCPError):
    """数据源调用失败（网络/超时/反爬）"""

    def __init__(self, message: str, source: str):
        super().__init__(f"[{source}] {message}")
        self.source = source


class RateLimitError(DataSourceError):
    """被限频"""

    def __init__(self, message: str, source: str, retry_after: int | None = None):
        super().__init__(message, source)
        self.retry_after = retry_after


class AuthError(DataSourceError):
    """认证失败"""

    def __init__(self, message: str, source: str = "iwencai"):
        super().__init__(message, source)
        self.source = source


class ParseError(DataSourceError):
    """返回数据解析失败（源改版/字段变更）"""

    def __init__(self, message: str, source: str):
        super().__init__(message, source)


class NotFoundError(StockMCPError):
    """股票代码不存在"""
    pass


class CacheError(StockMCPError):
    """缓存读写失败（不致命，会降级到直连源）"""
    pass
