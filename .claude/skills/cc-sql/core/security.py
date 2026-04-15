"""SQL 安全校验模块（从 app/security.py 提取并增强）"""
import re
from typing import Tuple

import sqlparse
from sqlparse.sql import Parenthesis
from sqlparse.tokens import Punctuation

from .exceptions import AggregateError, SecurityError, SelectStarError

# 允许的 SQL 语句类型
ALLOWED_STATEMENTS = {"SELECT", "SHOW", "DESCRIBE", "DESC", "EXPLAIN"}

# 危险的 SQL 关键字
DANGEROUS_KEYWORDS = {
    "INSERT", "UPDATE", "DELETE", "DROP", "TRUNCATE",
    "ALTER", "CREATE", "REPLACE", "RENAME", "GRANT",
    "REVOKE", "FLUSH", "KILL", "LOAD", "LOCK", "UNLOCK",
    "SET", "CALL", "EXECUTE", "PREPARE", "DEALLOCATE",
}

# 危险的 SQL 模式
DANGEROUS_PATTERNS = [
    r";\s*\w+",           # 多语句
    r"--\s",              # SQL 注释（MySQL 标准: -- 后接空格）
    r"--$",               # 行末 --
    r"#",                 # MySQL # 单行注释
    r"/\*[\s\S]*?\*/",    # 块注释（跨行匹配，用 [\s\S] 替代 .）
    r"INTO\s+OUTFILE",    # 导出到文件
    r"INTO\s+DUMPFILE",   # 导出到文件
    r"LOAD_FILE\s*\(",    # 读取文件
    r"INTO\s+@",          # 变量赋值（如 SELECT ... INTO @var）
    r"\bHANDLER\b",       # MySQL HANDLER 语法
    r"\bDO\b\s+",         # MySQL DO 语法
]


def validate_sql(sql: str, allowed_statements: set = None) -> Tuple[bool, str]:
    """校验 SQL 语句是否安全

    Args:
        sql: SQL 语句
        allowed_statements: 允许的语句类型集合，为 None 时使用默认值

    Returns:
        (is_valid, message) 元组
    """
    if allowed_statements is None:
        allowed_statements = ALLOWED_STATEMENTS

    if not sql or not sql.strip():
        return False, "SQL 语句不能为空"

    sql = sql.strip()

    # 检查危险模式
    for pattern in DANGEROUS_PATTERNS:
        if re.search(pattern, sql, re.IGNORECASE | re.MULTILINE):
            return False, "检测到危险的 SQL 模式"

    # 解析 SQL
    try:
        parsed = sqlparse.parse(sql)
    except Exception as e:
        return False, f"SQL 解析失败: {str(e)}"

    if not parsed:
        return False, "无法解析 SQL 语句"

    # 只允许单条语句
    if len(parsed) > 1:
        return False, "只允许执行单条 SQL 语句"

    statement = parsed[0]
    stmt_type = statement.get_type()

    # 如果无法识别类型，检查第一个非空白 token
    if stmt_type is None or stmt_type == "UNKNOWN":
        for token in statement.tokens:
            if token.is_whitespace:
                continue
            token_value = token.normalized.upper() if token.normalized else str(token).strip().upper()
            if token_value:
                stmt_type = token_value.split()[0]
                break

    if stmt_type:
        stmt_type = stmt_type.upper()

    if stmt_type not in allowed_statements:
        allowed_list = "/".join(sorted(allowed_statements))
        return False, f"不允许执行 {stmt_type} 语句，只允许 {allowed_list}"

    # 检查是否包含危险关键字
    sql_upper = sql.upper()
    for keyword in DANGEROUS_KEYWORDS:
        if re.search(rf"\b{keyword}\b", sql_upper):
            return False, f"SQL 语句包含危险关键字: {keyword}"

    return True, "校验通过"


def check_select_star(sql: str) -> Tuple[bool, str]:
    """检测 SELECT * 使用

    禁止: SELECT * FROM ..., SELECT t.* FROM ...
    允许: SELECT COUNT(*), EXISTS(SELECT * ...)（子查询中的 *）

    Returns:
        (has_star, message) — has_star=True 表示检测到违规的 SELECT *
    """
    try:
        parsed = sqlparse.parse(sql)
    except Exception:
        return False, ""

    if not parsed:
        return False, ""

    statement = parsed[0]
    return _check_tokens_for_star(statement.tokens, depth=0)


def _check_tokens_for_star(tokens, depth: int) -> Tuple[bool, str]:
    """递归检查 token 列表中是否有顶层 SELECT *

    depth=0 表示顶层，depth>0 表示在子查询/括号内
    """
    for token in tokens:
        # 括号内的内容递归检查，深度+1
        if isinstance(token, Parenthesis):
            # 子查询中的 SELECT * 是允许的（如 EXISTS(SELECT * ...)）
            continue

        # 跳过空白
        if token.is_whitespace:
            continue

        # 检查是否有 sqlparse 识别的子 token
        if hasattr(token, 'tokens'):
            has_star, msg = _check_tokens_for_star(token.tokens, depth)
            if has_star:
                return True, msg
            continue

        # 在顶层检查 Wildcard（*）token
        if depth == 0 and token.ttype is sqlparse.tokens.Wildcard:
            return True, "不允许使用 SELECT *，请指定具体列名"

        # 检查 t.* 模式：Name 后面跟 Punctuation(.) 再跟 Wildcard
        # sqlparse 会把 t.* 解析为一个 Identifier，在上面的 hasattr 分支处理

    return False, ""


# 聚合函数模式
AGGREGATE_PATTERNS = [
    r"\bCOUNT\s*\(",
    r"\bSUM\s*\(",
    r"\bAVG\s*\(",
    r"\bMIN\s*\(",
    r"\bMAX\s*\(",
    r"\bGROUP\s+BY\b",
]


def check_aggregate_query(sql: str) -> Tuple[bool, str]:
    """检测聚合查询是否包含 WHERE 条件

    聚合查询（COUNT/SUM/AVG/MIN/MAX/GROUP BY）必须包含 WHERE 条件，
    且条件字段应为索引字段（索引字段需调用方自行保证）。

    Returns:
        (has_violation, message) — has_violation=True 表示检测到违规
    """
    sql_upper = sql.upper().strip()

    # SHOW / DESCRIBE / EXPLAIN 不检查
    first_word = sql_upper.split()[0] if sql_upper else ""
    if first_word in ("SHOW", "DESCRIBE", "DESC", "EXPLAIN"):
        return False, ""

    # 检测是否包含聚合函数/GROUP BY
    has_aggregate = any(
        re.search(pattern, sql_upper) for pattern in AGGREGATE_PATTERNS
    )

    if not has_aggregate:
        return False, ""

    # 有聚合，检查是否有 WHERE 子句
    if not re.search(r"\bWHERE\b", sql_upper):
        return True, "聚合查询（COUNT/SUM/AVG/MIN/MAX/GROUP BY）必须包含 WHERE 条件且条件字段应为索引字段，禁止全表统计"

    return False, ""


def _ensure_limit(sql: str, max_rows: int) -> str:
    """如果 SQL 没有 LIMIT，自动追加；已有 LIMIT 则校验上限"""
    sql_upper = sql.upper().strip()

    # SHOW / DESCRIBE / EXPLAIN 不需要 LIMIT
    first_word = sql_upper.split()[0] if sql_upper else ""
    if first_word in ("SHOW", "DESCRIBE", "DESC", "EXPLAIN"):
        return sql

    # 已有 LIMIT：校验值是否超过上限
    # 支持两种格式：LIMIT count 或 LIMIT offset, count
    limit_match = re.search(r"\bLIMIT\s+(?:\d+\s*,\s*)?(\d+)", sql_upper)
    if limit_match:
        existing_limit = int(limit_match.group(1))

        # 检查非法值
        if existing_limit <= 0:
            raise SecurityError("LIMIT 值必须是正整数")

        if existing_limit > max_rows:
            # 替换为安全上限（保留 offset 部分）
            return re.sub(
                r"(?i)\bLIMIT\s+(?:(\d+)\s*,\s*)?(\d+)",
                lambda m: f"LIMIT {m.group(1)}, {max_rows}" if m.group(1) else f"LIMIT {max_rows}",
                sql,
                count=1,
            )
        return sql

    return f"{sql.rstrip().rstrip(';')} LIMIT {max_rows}"


def _strip_trailing_semicolons(sql: str) -> str:
    """去掉末尾分号"""
    return sql.rstrip().rstrip(";").rstrip()


def validate_and_prepare_sql(
    sql: str,
    max_rows: int = 1000,
    allow_select_star: bool = False,
    allowed_statements: set = None,
) -> str:
    """一站式 SQL 校验与准备

    流程：安全校验 → SELECT * 检查 → 聚合查询检查 → 去分号 → 补 LIMIT

    Returns:
        准备好的 SQL

    Raises:
        SecurityError: 安全校验不通过
        SelectStarError: 检测到顶层 SELECT *
    """
    # 1. 基础安全校验
    is_valid, message = validate_sql(sql, allowed_statements=allowed_statements)
    if not is_valid:
        raise SecurityError(message)

    # 2. SELECT * 检查
    if not allow_select_star:
        has_star, msg = check_select_star(sql)
        if has_star:
            raise SelectStarError(msg)

    # 3. 聚合查询检查
    has_violation, msg = check_aggregate_query(sql)
    if has_violation:
        raise AggregateError(msg)

    # 4. 去末尾分号
    sql = _strip_trailing_semicolons(sql)

    # 5. 自动补 LIMIT
    sql = _ensure_limit(sql, max_rows)

    return sql
