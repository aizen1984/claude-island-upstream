"""表索引缓存 - 文件+内存两级缓存，避免重复 SHOW INDEX 查询"""
import json
import re
import time
from pathlib import Path
from typing import Any, Dict, List, Optional, Set


class IndexCache:
    """索引信息缓存，文件持久化 + 内存热缓存"""

    def __init__(self, cache_dir: str, ttl: int = 86400):
        self._dir = Path(cache_dir)
        self._dir.mkdir(parents=True, exist_ok=True)
        self._ttl = ttl
        self._mem: Dict[str, Dict] = {}

    @staticmethod
    def _safe(s: str) -> str:
        return re.sub(r'[^a-zA-Z0-9_]', '_', s)

    def _key(self, env: str, database: str, table: str) -> str:
        return f"{self._safe(env)}__{self._safe(database)}__{self._safe(table)}"

    def _file(self, key: str) -> Path:
        return self._dir / f"{key}.json"

    def get(self, env: str, database: str, table: str) -> Optional[List[Dict]]:
        """获取缓存的索引，过期或未命中返回 None"""
        key = self._key(env, database, table)
        now = time.time()

        # 内存缓存
        if key in self._mem:
            if now - self._mem[key]["cached_at"] < self._ttl:
                return self._mem[key]["indexes"]
            del self._mem[key]

        # 文件缓存
        path = self._file(key)
        if path.exists():
            try:
                entry = json.loads(path.read_text(encoding="utf-8"))
                if now - entry["cached_at"] < self._ttl:
                    self._mem[key] = entry
                    return entry["indexes"]
                path.unlink()
            except (json.JSONDecodeError, KeyError, OSError):
                path.unlink(missing_ok=True)

        return None

    def put(self, env: str, database: str, table: str, indexes: List[Dict]):
        """写入缓存（内存 + 文件）"""
        key = self._key(env, database, table)
        entry = {
            "env": env,
            "database": database,
            "table": table,
            "indexes": indexes,
            "cached_at": time.time(),
        }
        self._mem[key] = entry
        try:
            self._file(key).write_text(
                json.dumps(entry, ensure_ascii=False, indent=2), encoding="utf-8"
            )
        except OSError:
            pass  # 写缓存失败不影响主流程

    def get_indexed_columns(self, env: str, database: str, table: str) -> Optional[Set[str]]:
        """获取已索引列名集合（小写）"""
        indexes = self.get(env, database, table)
        if indexes is None:
            return None
        return {col.lower() for idx in indexes for col in idx.get("columns", [])}

    def clear(self, table: str = None):
        """清理缓存：指定表名 or 全部"""
        if table:
            safe_table = self._safe(table)
            for f in self._dir.glob(f"*__{safe_table}.json"):
                f.unlink()
            self._mem = {
                k: v for k, v in self._mem.items()
                if not k.endswith(f"__{safe_table}")
            }
        else:
            for f in self._dir.glob("*.json"):
                f.unlink()
            self._mem.clear()

    def status(self) -> Dict[str, Any]:
        """缓存状态概览"""
        now = time.time()
        entries = []
        for f in sorted(self._dir.glob("*.json")):
            try:
                entry = json.loads(f.read_text(encoding="utf-8"))
                age = int(now - entry["cached_at"])
                entries.append({
                    "table": entry["table"],
                    "database": entry["database"],
                    "env": entry["env"],
                    "index_count": len(entry["indexes"]),
                    "age_seconds": age,
                    "expired": age >= self._ttl,
                })
            except (json.JSONDecodeError, KeyError, OSError):
                pass
        return {
            "cache_dir": str(self._dir),
            "ttl_seconds": self._ttl,
            "total": len(entries),
            "entries": entries,
        }
