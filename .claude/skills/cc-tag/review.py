#!/usr/bin/env python3
"""通过 Moka 网关执行代码评审通过"""
import argparse
import json
import os
import sys
import urllib.request
import urllib.error
from pathlib import Path

import yaml

_SCRIPT_DIR = Path(__file__).parent
_DEFAULT_CONFIG = _SCRIPT_DIR / "config.yaml"


def load_config():
    path = Path(os.getenv("STARK_TAG_CONFIG") or _DEFAULT_CONFIG)
    if not path.exists():
        print(f"❌ 配置文件不存在: {path}", file=sys.stderr)
        sys.exit(1)
    with open(path, "r", encoding="utf-8") as f:
        return yaml.safe_load(f)


def load_token(config):
    token_file = config["connection"]["token_file"]
    try:
        with open(token_file, "r", encoding="utf-8") as f:
            data = json.load(f)
    except FileNotFoundError:
        print(f"❌ Token 文件不存在: {token_file}", file=sys.stderr)
        print("请先登录 moka.dmz.prod.caijj.net", file=sys.stderr)
        sys.exit(1)
    token = data.get("xToken")
    if not token:
        print(f"❌ Token 文件中缺少 xToken 字段: {token_file}", file=sys.stderr)
        sys.exit(1)
    return token


def approve_review(code_review_id, token, config):
    """调用代码评审通过接口"""
    base_url = config["connection"]["base_url"]
    timeout = config["connection"].get("timeout", 15)
    url = f"{base_url}/bettercdsmgr/bettercds/code-review/{code_review_id}/apply"

    headers = {
        "Content-Type": "application/json",
        "X-TOKEN": token,
    }

    req = urllib.request.Request(url, data=b"{}", headers=headers, method="PUT")

    try:
        with urllib.request.urlopen(req, timeout=timeout) as response:
            body = response.read().decode("utf-8")
            if body:
                return json.loads(body)
            return {"success": True, "status": response.status}
    except urllib.error.HTTPError as e:
        error_body = e.read().decode("utf-8") if e.fp else ""
        return {"error": True, "status": e.code, "reason": e.reason, "body": error_body}
    except urllib.error.URLError as e:
        return {"error": True, "reason": str(e.reason)}


def main():
    parser = argparse.ArgumentParser(description="代码评审通过")
    parser.add_argument("code_review_id", help="代码评审 ID（如 140373）")
    args = parser.parse_args()

    config = load_config()
    token = load_token(config)

    print(f">>> 评审通过: codeReviewId={args.code_review_id}")
    print()

    result = approve_review(args.code_review_id, token, config)
    print(json.dumps(result, ensure_ascii=False, indent=2, default=str))


if __name__ == "__main__":
    main()
