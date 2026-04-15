#!/usr/bin/env python3
"""获取目标用户的 idaas x-token"""
import argparse
import json
import sys

from core.client import IdaasTokenClient
from core.config import load_config


def main():
    parser = argparse.ArgumentParser(description="获取目标用户的 idaas x-token")
    parser.add_argument("user_id", help="目标用户的租户账号 ID")
    parser.add_argument("--env", choices=["sit", "prod"], default=None, help="环境（默认 sit）")
    parser.add_argument("--verify", action="store_true", help="获取后验证 token 对应的用户信息")
    parser.add_argument("--config", help="自定义配置文件路径")
    args = parser.parse_args()

    try:
        config = load_config(args.config, env=args.env)
        client = IdaasTokenClient(config)

        result = client.toggle(args.user_id)

        if args.verify:
            userinfo = client.verify(result["x_token"])
            result["verified_userinfo"] = userinfo.get("userinfo")

        print(json.dumps(result, ensure_ascii=False, indent=2))

    except Exception as e:
        error = {"success": False, "error": str(e)}
        print(json.dumps(error, ensure_ascii=False, indent=2), file=sys.stderr)
        sys.exit(1)


if __name__ == "__main__":
    main()
