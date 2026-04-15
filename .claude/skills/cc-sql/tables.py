#!/usr/bin/env python3
"""列出表"""
import argparse
import sys

from core.client import create_client
from core.config import load_config
from core.exceptions import SkillError
from core.formatter import output_error, output_success


def main():
    parser = argparse.ArgumentParser(description="列出数据库的表")
    parser.add_argument("-i", "--instance", help="实例名")
    parser.add_argument("-d", "--database", help="库名")
    parser.add_argument("--filter", help="模糊过滤表名")
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
            tables = client.get_tables(instance, database)
        finally:
            client.close()

        # 过滤
        if args.filter:
            keyword = args.filter.lower()
            tables = [t for t in tables if keyword in t.lower()]

        data = {
            "success": True,
            "instance": instance,
            "database": database,
            "tables": tables,
            "count": len(tables),
        }

        columns = ["tableName"]
        rows = [[t] for t in tables]
        output_success(data, fmt=fmt, indent=config.output.json_indent,
                       columns=columns, rows=rows,
                       max_column_width=config.output.max_column_width)

    except SkillError as e:
        output_error(e.message, e.code)
        sys.exit(1)
    except Exception as e:
        output_error(str(e))
        sys.exit(1)


if __name__ == "__main__":
    main()
