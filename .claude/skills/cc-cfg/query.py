#!/usr/bin/env python3
"""查询配置中心"""
import argparse
import json
import sys

from core.client import CfgClient
from core.config import load_config


def main():
    parser = argparse.ArgumentParser(description="查询配置中心")
    parser.add_argument("key", help="配置 key")
    parser.add_argument("-a", "--app", help="应用名（默认 vipship）")
    parser.add_argument("--config", help="自定义配置文件路径")
    args = parser.parse_args()

    try:
        config = load_config(args.config)
        app_name = args.app or config.defaults.app_name

        client = CfgClient(config)
        result = client.query(args.key, app_name)

        print(json.dumps(result, ensure_ascii=False, indent=2, default=str))

    except Exception as e:
        error = {"success": False, "error": str(e)}
        print(json.dumps(error, ensure_ascii=False, indent=2), file=sys.stderr)
        sys.exit(1)


if __name__ == "__main__":
    main()
