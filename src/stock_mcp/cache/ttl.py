"""TTL 计算 - 不同数据类型用不同 TTL 策略

**2026-06-12 简化**: 砍掉短期缓存 (realtime_quote/kline_minute/news), 只留
长期缓存 (kline_daily/fundamental).

理由:
- realtime_quote 3s TTL 实际命中率 ~0 (LLM 不会 3 秒内查同一只 2 次),
  写盘 + 索引全浪费
- kline_minute 60s / news 10 分钟 类似, 命中率低
- kline_daily 1 天 + fundamental 1 天 真实价值: 用户反复查"过去 30 天日线"

效果:
- 1 年 db 大小: 250 MB → ~5-10 MB
- LLM 体验几乎无变化 (本来短期命中率就低)
- 架构简化: 短期 cache 调用删掉
"""

from dataclasses import dataclass


@dataclass
class TTLConfig:
    kline_daily: int = 86400  # 日线 1 天 (核心缓存)
    fundamental: int = 86400  # 基本面 1 天 (核心缓存)


class TTLCalculator:
    """将绝对时间映射到 TTL 桶（用于缓存 key）"""

    def __init__(self, config: TTLConfig | None = None):
        self._config = config or TTLConfig()

    def ttl_seconds(self, data_type: str) -> int:
        return {
            "kline_daily": self._config.kline_daily,
            "fundamental": self._config.fundamental,
        }.get(data_type, 86400)  # 默认 1 天 (安全兜底)

    def bucket_for(self, data_type: str, base_time: float | None = None) -> int:
        """计算缓存桶时间戳（同一桶内复用同一缓存）"""
        ttl = self.ttl_seconds(data_type)
        t = base_time if base_time is not None else __import__("time").time()
        return int(t // ttl) * ttl
