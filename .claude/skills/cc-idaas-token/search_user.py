#!/usr/bin/env python3
"""按姓名搜索 idaas 用户"""
import argparse
import json
import sys

from core.client import IdaasTokenClient
from core.config import load_config


def main():
    parser = argparse.ArgumentParser(description="按姓名搜索 idaas 用户")
    parser.add_argument("name", help="用户姓名（支持模糊搜索）")
    parser.add_argument("--env", choices=["sit", "prod"], default=None, help="环境（默认 sit）")
    parser.add_argument("--size", type=int, default=10, help="返回数量（默认 10）")
    parser.add_argument("--config", help="自定义配置文件路径")
    args = parser.parse_args()

    try:
        config = load_config(args.config, env=args.env)
        client = IdaasTokenClient(config)
        result = client.search_users(args.name, page_size=args.size)
        print(json.dumps(result, ensure_ascii=False, indent=2))

    except Exception as e:
        error = {"success": False, "error": str(e)}
        print(json.dumps(error, ensure_ascii=False, indent=2), file=sys.stderr)
        sys.exit(1)


if __name__ == "__main__":
    main()
