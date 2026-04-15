#!/usr/bin/env python3
"""索引缓存管理"""
import argparse
import sys

from core.config import load_config
from core.exceptions import SkillError
from core.formatter import output_error, output_success
from core.index_cache import IndexCache


def main():
    parser = argparse.ArgumentParser(description="索引缓存管理")
    parser.add_argument("action", choices=["status", "clear"], help="操作类型")
    parser.add_argument("--table", help="指定表名（仅 clear 时有效）")
    parser.add_argument("--env", help="环境（prod/sit）")
    parser.add_argument("--config", help="自定义配置文件路径")
    args = parser.parse_args()

    try:
        config = load_config(args.config, env=args.env)
        cache = IndexCache(config.cache.dir, config.cache.ttl)

        if args.action == "status":
            output_success(cache.status(), fmt="json", indent=config.output.json_indent)
        elif args.action == "clear":
            cache.clear(table=args.table)
            target = f"表 {args.table}" if args.table else "全部"
            output_success(
                {"success": True, "message": f"已清理缓存: {target}"},
                fmt="json",
                indent=config.output.json_indent,
            )

    except SkillError as e:
        output_error(e.message, e.code)
        sys.exit(1)
    except Exception as e:
        output_error(str(e))
        sys.exit(1)


if __name__ == "__main__":
    main()
