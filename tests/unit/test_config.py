from stock_mcp.config import Settings

# 显式传 _env_file=None 避免项目根 .env 干扰测试
NO_ENV = {"_env_file": None}


def test_settings_default_values(monkeypatch):
    monkeypatch.delenv("LOG_LEVEL", raising=False)
    monkeypatch.delenv("TDX_PATH", raising=False)
    monkeypatch.delenv("IWENCAI_COOKIE", raising=False)
    s = Settings(**NO_ENV)
    assert s.log_level == "INFO"
    assert s.tdx_path == ""


def test_settings_loads_tdx_path(monkeypatch):
    monkeypatch.setenv("TDX_PATH", "D:/tdx")
    s = Settings(**NO_ENV)
    assert s.tdx_path == "D:/tdx"


def test_settings_iwencai_cookie_optional(monkeypatch):
    monkeypatch.delenv("IWENCAI_COOKIE", raising=False)
    s = Settings(**NO_ENV)
    assert s.iwencai_cookie is None


def test_settings_iwencai_cookie_loaded(monkeypatch):
    monkeypatch.setenv("IWENCAI_COOKIE", "v=123; path=/")
    s = Settings(**NO_ENV)
    assert s.iwencai_cookie == "v=123; path=/"


def test_settings_cache_db_path_default(monkeypatch, temp_cache_dir):
    monkeypatch.setenv("CACHE_DIR", str(temp_cache_dir))
    s = Settings(**NO_ENV)
    assert s.cache_db_path.name == "stock-mcp.db"
