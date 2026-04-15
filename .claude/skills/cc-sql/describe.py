#!/usr/bin/env python3
"""表完整描述（字段+索引）"""
import argparse
import sys

from core.client import create_client
from core.config import load_config
from core.exceptions import SkillError
from core.formatter import format_table, output_error, output_success


def main():
    parser = argparse.ArgumentParser(description="表完整描述（字段+索引）")
    parser.add_argument("table", help="表名")
    parser.add_argument("-i", "--instance", help="实例名")
    parser.add_argument("-d", "--database", help="库名")
    parser.add_argument("--indexes-only", action="store_true", help="只显示索引")
    parser.add_argument("--format", choices=["json", "table"], help="输出格式")
    parser.add_argument("--env", help="环境（prod/sit），默认 prod")
    parser.add_argument("--config", help="自定义配置文件路径")
    args = parser.parse_args()

    try:
        config = load_config(args.config, env=args.env)
        instance = args.instance or config.defaults.instance_name
        database = args.database or config.defaults.schema_name
        fmt = args.format or config.output.format

        client = create_client(config)
        try:
            if args.indexes_only:
                columns_data = []
            else:
                columns_data = client.get_columns(database, args.table, instance_name=instance)
            indexes_data = client.get_indexes(database, args.table, instance_name=instance)
        finally:
            client.close()

        # 索引信息写入缓存（供后续 query.py 复用）
        if config.cache.enabled and indexes_data:
            from core.index_cache import IndexCache
            cache = IndexCache(config.cache.dir, config.cache.ttl)
            cache.put(config.env_name, database, args.table, indexes_data)

        data = {
            "success": True,
            "instance": instance,
            "database": database,
            "table": args.table,
        }
        if not args.indexes_only:
            data["columns"] = columns_data
        data["indexes"] = indexes_data

        if fmt == "table":
            parts = []
            if not args.indexes_only and columns_data:
                col_headers = ["name", "type", "nullable", "key", "default", "comment"]
                col_rows = [
                    [c["name"], c["type"], c["nullable"], c.get("key", ""), c.get("default", ""), c.get("comment", "")]
                    for c in columns_data
                ]
                parts.append(f"=== 字段 ({len(columns_data)}) ===")
                parts.append(format_table(col_headers, col_rows, config.output.max_column_width))

            if indexes_data:
                idx_headers = ["name", "type", "unique", "columns"]
                idx_rows = [
                    [idx["name"], idx["type"], idx["unique"], ", ".join(idx["columns"])]
                    for idx in indexes_data
                ]
                parts.append(f"\n=== 索引 ({len(indexes_data)}) ===")
                parts.append(format_table(idx_headers, idx_rows, config.output.max_column_width))

            print("\n".join(parts))
        else:
            output_success(data, fmt="json", indent=config.output.json_indent)

    except SkillError as e:
        output_error(e.message, e.code)
        sys.exit(1)
    except Exception as e:
        output_error(str(e))
        sys.exit(1)


if __name__ == "__main__":
    main()
