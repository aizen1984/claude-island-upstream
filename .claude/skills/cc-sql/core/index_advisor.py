"""索引建议 - 查询前分析 WHERE 列与索引的匹配情况"""
import re
import sys
from typing import Any, Dict, List, Optional, Set

from .index_cache import IndexCache

# 列名提取时排除的 SQL 关键字
_SQL_KEYWORDS = {
    "AND", "OR", "NOT", "NULL", "TRUE", "FALSE", "BETWEEN", "IN",
    "LIKE", "IS", "EXISTS", "CASE", "WHEN", "THEN", "ELSE", "END",
    "SELECT", "FROM", "WHERE", "GROUP", "ORDER", "LIMIT", "HAVING",
}


def extract_tables(sql: str) -> List[str]:
    """从 FROM/JOIN 子句提取表名（去重保序）"""
    normalized = " ".join(sql.split())
    matches = re.findall(
        r"(?:FROM|JOIN)\s+`?(\w+)`?", normalized, re.IGNORECASE
    )
    seen: Set[str] = set()
    result = []
    for t in matches:
        low = t.lower()
        if low not in seen:
            seen.add(low)
            result.append(t)
    return result


def extract_where_columns(sql: str) -> Set[str]:
    """从 WHERE 子句提取条件列名（支持别名前缀 t.col）"""
    m = re.search(
        r"\bWHERE\b\s+(.+?)(?:\bGROUP\b|\bORDER\b|\bLIMIT\b|\bHAVING\b|\bUNION\b|$)",
        sql,
        re.IGNORECASE | re.DOTALL,
    )
    if not m:
        return set()

    clause = m.group(1)
    cols: Set[str] = set()

    # 匹配比较运算符、IN、BETWEEN、LIKE、IS 左侧的列名
    patterns = [
        r"(?<!\w)`?(?:\w+\.)?(\w+)`?\s*(?:=|!=|<>|>=?|<=?)",
        r"(?<!\w)`?(?:\w+\.)?(\w+)`?\s+(?:NOT\s+)?IN\s*\(",
        r"(?<!\w)`?(?:\w+\.)?(\w+)`?\s+BETWEEN\b",
        r"(?<!\w)`?(?:\w+\.)?(\w+)`?\s+(?:NOT\s+)?LIKE\b",
        r"(?<!\w)`?(?:\w+\.)?(\w+)`?\s+IS\s+",
    ]
    for p in patterns:
        for match in re.finditer(p, clause, re.IGNORECASE):
            c = match.group(1)
            # 过滤 SQL 关键字和纯数字
            if c.upper() not in _SQL_KEYWORDS and re.match(r"^[a-zA-Z_]", c):
                cols.add(c.lower())
    return cols


def is_select(sql: str) -> bool:
    """是否为 SELECT 查询（排除 SHOW/DESCRIBE/EXPLAIN）"""
    first = sql.strip().split()[0].upper() if sql.strip() else ""
    return first == "SELECT"


def analyze(
    sql: str,
    cache: IndexCache,
    client: Any,
    env: str,
    instance: str,
    database: str,
) -> Optional[Dict[str, Any]]:
    """分析查询索引使用情况

    - 单表：检查 WHERE 列是否命中索引，输出警告
    - 多表：仅展示各表索引（无法确定 WHERE 列归属）

    Returns:
        index_check dict 或 None（非 SELECT / 无法提取表名）
    """
    if not is_select(sql):
        return None

    tables = extract_tables(sql)
    if not tables:
        return None

    where_cols = extract_where_columns(sql)
    result: Dict[str, Any] = {}

    for table in tables:
        indexes = cache.get(env, database, table)
        hit = indexes is not None

        if indexes is None:
            try:
                indexes = client.get_indexes(database, table, instance_name=instance)
                cache.put(env, database, table, indexes)
            except Exception:
                continue

        indexed_cols = {
            col.lower() for idx in indexes for col in idx.get("columns", [])
        }

        info: Dict[str, Any] = {
            "indexes": [
                {
                    "name": i["name"],
                    "columns": i["columns"],
                    "unique": i.get("unique", False),
                }
                for i in indexes
            ],
            "indexed_columns": sorted(indexed_cols),
            "cache_hit": hit,
        }

        # 单表查询才做 WHERE 列匹配（多表无法确定列归属）
        if len(tables) == 1 and where_cols:
            matched = where_cols & indexed_cols
            unmatched = where_cols - indexed_cols
            info["where_columns"] = sorted(where_cols)
            info["matched"] = sorted(matched)
            info["unmatched"] = sorted(unmatched)
            if unmatched:
                info["warning"] = (
                    f"WHERE 中 {sorted(unmatched)} 未命中索引，大表可能超时。"
                    f" 可用索引列: {sorted(indexed_cols)}"
                )
                print(
                    f"\u26a0\ufe0f  索引预检: {info['warning']}", file=sys.stderr
                )

        result[table] = info

    return result if result else None
