#!/usr/bin/env python3
"""执行 SQL 查询（核心）"""
import argparse
import sys

from core.client import create_client
from core.config import load_config
from core.exceptions import SkillError
from core.formatter import output_error, output_success
from core.index_advisor import analyze as analyze_indexes
from core.index_cache import IndexCache
from core.security import validate_and_prepare_sql


def _read_sql(args) -> str:
    """从参数、文件或 stdin 读取 SQL"""
    if args.sql:
        return args.sql

    if args.file:
        with open(args.file, "r", encoding="utf-8") as f:
            return f.read().strip()

    # 尝试从 stdin 读取（非 TTY 时）
    if not sys.stdin.isatty():
        return sys.stdin.read().strip()

    return ""


def main():
    parser = argparse.ArgumentParser(description="执行 SQL 查询")
    parser.add_argument("sql", nargs="?", help="SQL 语句")
    parser.add_argument("-i", "--instance", help="实例名")
    parser.add_argument("-d", "--database", help="库名")
    parser.add_argument("--file", help="从文件读取 SQL")
    parser.add_argument("--limit", type=int, help="覆盖最大行数限制")
    parser.add_argument("--format", choices=["json", "table"], help="输出格式")
    parser.add_argument("--env", help="环境（prod/sit），默认 prod")
    parser.add_argument("--config", help="自定义配置文件路径")
    parser.add_argument("--no-index-check", action="store_true", help="跳过索引预检")
    args = parser.parse_args()

    try:
        config = load_config(args.config, env=args.env)
        instance = args.instance or config.defaults.instance_name
        database = args.database or config.defaults.schema_name
        fmt = args.format or config.output.format

        # 校验 LIMIT 参数
        if args.limit is not None:
            if args.limit <= 0:
                output_error("--limit 必须是正整数", "INPUT_ERROR")
                sys.exit(1)
            max_rows = min(args.limit, config.safety.max_rows)
        else:
            max_rows = config.safety.max_rows

        sql = _read_sql(args)
        if not sql:
            output_error("请提供 SQL 语句（参数、--file 或 stdin）", "INPUT_ERROR")
            sys.exit(1)

        # 安全校验 + 准备
        prepared_sql = validate_and_prepare_sql(
            sql,
            max_rows=max_rows,
            allow_select_star=config.safety.allow_select_star,
            allowed_statements=set(config.safety.allowed_statements),
        )

        # 执行查询（含索引预检）
        client = create_client(config)
        index_check = None
        try:
            # 索引预检：查缓存 or SHOW INDEX，分析 WHERE 列匹配
            if config.cache.enabled and not args.no_index_check:
                cache = IndexCache(config.cache.dir, config.cache.ttl)
                index_check = analyze_indexes(
                    prepared_sql, cache, client,
                    config.env_name, instance, database,
                )

            result = client.execute_sql(database, prepared_sql, instance_name=instance)
        finally:
            client.close()

        result["instance"] = instance
        result["database"] = database
        if index_check:
            result["index_check"] = index_check

        output_success(
            result,
            fmt=fmt,
            indent=config.output.json_indent,
            columns=result.get("columns"),
            rows=result.get("rows"),
            max_column_width=config.output.max_column_width,
        )

    except SkillError as e:
        output_error(e.message, e.code)
        sys.exit(1)
    except Exception as e:
        output_error(str(e))
        sys.exit(1)


if __name__ == "__main__":
    main()
