#!/usr/bin/env python3
"""通过 Moka 网关创建 feature tag"""
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

from history import append_record, show_history


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


def fetch_jira_summary(req_id, token, config):
    """通过 Moka 网关查询 JIRA 需求详情，返回 summary"""
    base_url = config["connection"]["base_url"]
    timeout = config["connection"].get("timeout", 15)
    url = f"{base_url}/bettercdsmgr/bettercds/jira/detail/{req_id}"
    headers = {
        "Content-Type": "application/json",
        "X-TOKEN": token,
    }
    req = urllib.request.Request(url, headers=headers, method="GET")
    try:
        with urllib.request.urlopen(req, timeout=timeout) as response:
            result = json.loads(response.read().decode("utf-8"))
    except urllib.error.HTTPError as e:
        print(f"❌ 查询 JIRA 失败: HTTP {e.code} - {e.reason}", file=sys.stderr)
        sys.exit(1)
    except urllib.error.URLError as e:
        print(f"❌ 查询 JIRA 网络错误: {e.reason}", file=sys.stderr)
        sys.exit(1)

    summary = result.get("fields", {}).get("summary")
    if not summary:
        print(f"❌ 未找到需求 {req_id}，请检查需求号是否正确", file=sys.stderr)
        sys.exit(1)

    return summary


def create_tag(feature_name, req_id, desc, app_name, token, config,
               story="common", code_analysis=True):
    """调用 Moka git-tag/featureTag 接口"""
    base_url = config["connection"]["base_url"]
    timeout = config["connection"].get("timeout", 15)
    defaults = config.get("defaults", {})
    user_id = defaults.get("user_id", "")
    user_name = defaults.get("user_name", "")

    url = f"{base_url}/bettercdsmgr/bettercds/git-tag/featureTag"

    body = {
        "featureName": feature_name,
        "req": [{
            "key": req_id,
            "jiraId": req_id,
            "desc": desc,
            "label": f"{req_id}:{desc}",
            "value": req_id,
        }],
        "story": story,
        "codeAnalysis": code_analysis,
        "user": [{
            "userId": user_id,
            "userName": user_name,
        }],
        "appName": app_name,
    }

    headers = {
        "Content-Type": "application/json",
        "X-TOKEN": token,
    }

    data = json.dumps(body, ensure_ascii=False).encode("utf-8")
    req = urllib.request.Request(url, data=data, headers=headers, method="POST")

    try:
        with urllib.request.urlopen(req, timeout=timeout) as response:
            result = json.loads(response.read().decode("utf-8"))
            return result
    except urllib.error.HTTPError as e:
        error_body = e.read().decode("utf-8") if e.fp else ""
        return {"error": True, "status": e.code, "reason": e.reason, "body": error_body}
    except urllib.error.URLError as e:
        return {"error": True, "reason": str(e.reason)}


def main():
    parser = argparse.ArgumentParser(description="通过 Moka 网关创建 feature tag")
    parser.add_argument("app_name", help="应用名（如 vipship）")
    parser.add_argument("feature_name", help="分支名（如 feature_common_release）")
    parser.add_argument("req_id", help="JIRA 需求号（如 REQ-34449）")
    parser.add_argument("story", help="功能描述/备注（如 common、会员权益优化）")
    args = parser.parse_args()

    config = load_config()
    token = load_token(config)

    # 展示该项目的历史记录
    show_history(app=args.app_name, branch=args.feature_name)

    # 自动查询需求描述
    print(f">>> 查询需求 {args.req_id} ...")
    desc = fetch_jira_summary(args.req_id, token, config)

    print(f">>> 打 tag: {args.app_name} / {args.feature_name}")
    print(f">>> 需求: {args.req_id} - {desc}")
    print(f">>> 功能描述: {args.story}")
    print()

    result = create_tag(args.feature_name, args.req_id, desc, args.app_name, token, config, story=args.story)
    print(json.dumps(result, ensure_ascii=False, indent=2, default=str))

    # 记录历史
    success = not result.get("error", False)
    code_review_id = None
    if isinstance(result, dict):
        cr = result.get("codeReview") or {}
        code_review_id = cr.get("codeReviewId")
    append_record(args.app_name, args.feature_name, args.req_id, args.story, desc,
                  code_review_id=code_review_id, success=success)


if __name__ == "__main__":
    main()
