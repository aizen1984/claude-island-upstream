#!/usr/bin/env python3
"""列出可用数据库（instance/schema）"""
import argparse
import sys

from core.client import create_client
from core.config import load_config
from core.exceptions import SkillError
from core.formatter import output_error, output_success


def main():
    parser = argparse.ArgumentParser(description="列出可用数据库")
    parser.add_argument("--filter", help="模糊过滤关键字")
    parser.add_argument("--format", choices=["json", "table"], help="输出格式")
    parser.add_argument("--env", help="环境（prod/sit），默认 prod")
    parser.add_argument("--config", help="自定义配置文件路径")
    args = parser.parse_args()

    try:
        config = load_config(args.config, env=args.env)
        fmt = args.format or config.output.format
        client = create_client(config)

        try:
            schemas = client.get_schemas()
        finally:
            client.close()

        # 过滤
        if args.filter:
            keyword = args.filter.lower()
            schemas = [
                s for s in schemas
                if keyword in s["instanceName"].lower() or keyword in s["schemaName"].lower()
            ]

        data = {
            "success": True,
            "databases": schemas,
            "count": len(schemas),
        }

        columns = ["instanceName", "schemaName"]
        rows = [[s["instanceName"], s["schemaName"]] for s in schemas]
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
