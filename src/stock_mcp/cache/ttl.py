"""TTL 计算 - 不同数据类型用不同 TTL 策略"""

from dataclasses import dataclass


@dataclass
class TTLConfig:
    realtime_quote: int = 3  # 实时行情 3 秒
    kline_daily: int = 86400  # 日线 1 天
    kline_minute: int = 60  # 分钟线 60 秒
    fundamental: int = 86400  # 基本面 1 天
    news: int = 600  # 资讯 10 分钟


class TTLCalculator:
    """将绝对时间映射到 TTL 桶（用于缓存 key）"""

    def __init__(self, config: TTLConfig | None = None):
        self._config = config or TTLConfig()

    def ttl_seconds(self, data_type: str) -> int:
        return {
            "realtime_quote": self._config.realtime_quote,
            "kline": self._config.kline_minute,
            "kline_daily": self._config.kline_daily,
            "fundamental": self._config.fundamental,
            "news": self._config.news,
        }.get(data_type, 60)

    def bucket_for(self, data_type: str, base_time: float | None = None) -> int:
        """计算缓存桶时间戳（同一桶内复用同一缓存）"""
        ttl = self.ttl_seconds(data_type)
        t = base_time if base_time is not None else __import__("time").time()
        return int(t // ttl) * ttl
