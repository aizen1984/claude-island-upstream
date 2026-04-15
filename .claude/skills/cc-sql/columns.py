#!/usr/bin/env python3
"""查看表字段"""
import argparse
import sys

from core.client import create_client
from core.config import load_config
from core.exceptions import SkillError
from core.formatter import output_error, output_success


def main():
    parser = argparse.ArgumentParser(description="查看表字段")
    parser.add_argument("table", help="表名")
    parser.add_argument("-i", "--instance", help="实例名")
    parser.add_argument("-d", "--database", help="库名")
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
            cols = client.get_columns(database, args.table, instance_name=instance)
        finally:
            client.close()

        data = {
            "success": True,
            "instance": instance,
            "database": database,
            "table": args.table,
            "columns": cols,
            "count": len(cols),
        }

        headers = ["name", "type", "nullable", "key", "default", "comment"]
        rows = [
            [c["name"], c["type"], c["nullable"], c.get("key", ""), c.get("default", ""), c.get("comment", "")]
            for c in cols
        ]
        output_success(data, fmt=fmt, indent=config.output.json_indent,
                       columns=headers, rows=rows,
                       max_column_width=config.output.max_column_width)

    except SkillError as e:
        output_error(e.message, e.code)
        sys.exit(1)
    except Exception as e:
        output_error(str(e))
        sys.exit(1)


if __name__ == "__main__":
    main()
