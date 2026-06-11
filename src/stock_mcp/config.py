"""全局配置 - 通过环境变量加载"""

from pathlib import Path

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    # 通达信路径
    tdx_path: str = ""

    # 日志
    log_level: str = "INFO"

    # 缓存
    cache_dir: Path = Path("./.cache")
    cache_db_path: Path | None = None  # 默认 = cache_dir/stock-mcp.db

    # iwencai
    iwencai_cookie: str | None = None

    # 代理
    http_proxy: str | None = None

    def model_post_init(self, __context):
        if self.cache_db_path is None:
            self.cache_db_path = self.cache_dir / "stock-mcp.db"


_settings: Settings | None = None


def get_settings() -> Settings:
    """获取全局 settings 单例"""
    global _settings
    if _settings is None:
        _settings = Settings()
    return _settings


def reset_settings() -> None:
    """重置单例（用于测试）"""
    global _settings
    _settings = None
