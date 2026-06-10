from stock_mcp.config import Settings


def test_settings_default_values(monkeypatch):
    monkeypatch.delenv("LOG_LEVEL", raising=False)
    s = Settings()
    assert s.log_level == "INFO"
    assert s.tdx_path == ""


def test_settings_loads_tdx_path(monkeypatch):
    monkeypatch.setenv("TDX_PATH", "D:/tdx")
    s = Settings()
    assert s.tdx_path == "D:/tdx"


def test_settings_iwencai_cookie_optional(monkeypatch):
    monkeypatch.delenv("IWENCAI_COOKIE", raising=False)
    s = Settings()
    assert s.iwencai_cookie is None


def test_settings_iwencai_cookie_loaded(monkeypatch):
    monkeypatch.setenv("IWENCAI_COOKIE", "v=123; path=/")
    s = Settings()
    assert s.iwencai_cookie == "v=123; path=/"


def test_settings_cache_db_path_default(monkeypatch, temp_cache_dir):
    monkeypatch.setenv("CACHE_DIR", str(temp_cache_dir))
    s = Settings()
    assert s.cache_db_path.name == "stock-mcp.db"
