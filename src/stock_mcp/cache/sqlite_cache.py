"""基于 SQLite 的缓存 - 异步、TTL、模式删除"""
import time
import fnmatch
import aiosqlite
from pathlib import Path
from typing import Optional
from ..domain.errors import CacheError
from ..logging_setup import get_logger

log = get_logger(__name__)


class SQLiteCache:
    def __init__(self, db_path: Path):
        self._db_path = db_path
        self._db_path.parent.mkdir(parents=True, exist_ok=True)
        self._initialized = False

    async def _ensure_schema(self):
        if self._initialized:
            return
        async with aiosqlite.connect(self._db_path) as db:
            await db.execute("""
                CREATE TABLE IF NOT EXISTS cache (
                    key TEXT PRIMARY KEY,
                    value TEXT NOT NULL,
                    expire_at REAL NOT NULL
                )
            """)
            await db.execute("CREATE INDEX IF NOT EXISTS idx_expire ON cache(expire_at)")
            await db.commit()
        self._initialized = True

    async def get(self, key: str) -> Optional[str]:
        try:
            await self._ensure_schema()
            async with aiosqlite.connect(self._db_path) as db:
                cursor = await db.execute(
                    "SELECT value, expire_at FROM cache WHERE key = ?", (key,)
                )
                row = await cursor.fetchone()
                if not row:
                    return None
                value, expire_at = row
                if time.time() > expire_at:
                    await db.execute("DELETE FROM cache WHERE key = ?", (key,))
                    await db.commit()
                    return None
                return value
        except Exception as e:
            log.warning("cache_get_failed", key=key, error=str(e))
            return None

    async def set(self, key: str, value: str, ttl: int) -> None:
        try:
            await self._ensure_schema()
            expire_at = time.time() + ttl
            async with aiosqlite.connect(self._db_path) as db:
                await db.execute(
                    "INSERT OR REPLACE INTO cache (key, value, expire_at) VALUES (?, ?, ?)",
                    (key, value, expire_at),
                )
                await db.commit()
        except Exception as e:
            log.warning("cache_set_failed", key=key, error=str(e))

    async def delete_pattern(self, pattern: str) -> int:
        try:
            await self._ensure_schema()
            async with aiosqlite.connect(self._db_path) as db:
                cursor = await db.execute("SELECT key FROM cache")
                rows = await cursor.fetchall()
                keys_to_delete = [r[0] for r in rows if fnmatch.fnmatch(r[0], pattern)]
                if keys_to_delete:
                    placeholders = ",".join("?" * len(keys_to_delete))
                    await db.execute(
                        f"DELETE FROM cache WHERE key IN ({placeholders})", keys_to_delete
                    )
                    await db.commit()
                return len(keys_to_delete)
        except Exception as e:
            log.warning("cache_delete_pattern_failed", pattern=pattern, error=str(e))
            return 0
