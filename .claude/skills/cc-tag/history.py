#!/usr/bin/env python3
"""cc-tag 历史记录管理（项目级）"""
import json
import os
import sys
from datetime import datetime
from pathlib import Path

_SCRIPT_DIR = Path(__file__).parent
_DEFAULT_HISTORY_FILE = _SCRIPT_DIR / "history.jsonl"
_MAX_RECORDS = 10


def _history_path():
    return Path(os.getenv("STARK_TAG_HISTORY") or _DEFAULT_HISTORY_FILE)


def load_history():
    """读取全部历史记录，返回 list[dict]"""
    path = _history_path()
    if not path.exists():
        return []
    records = []
    for line in path.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if line:
            try:
                records.append(json.loads(line))
            except json.JSONDecodeError:
                continue
    return records


def append_record(app, branch, req_id, story, desc, code_review_id=None, success=True):
    """追加一条记录，超过上限自动淘汰最旧的"""
    record = {
        "ts": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        "app": app,
        "branch": branch,
        "req_id": req_id,
        "story": story,
        "desc": desc,
        "code_review_id": code_review_id,
        "success": success,
    }
    records = load_history()
    records.append(record)
    # 超过上限，淘汰最旧的
    if len(records) > _MAX_RECORDS:
        records = records[-_MAX_RECORDS:]
    _save(records)
    return record


def show_history(app=None, branch=None):
    """打印历史记录（可按 app/branch 过滤），返回匹配条数"""
    records = load_history()
    if app:
        records = [r for r in records if r.get("app") == app]
    if branch:
        records = [r for r in records if r.get("branch") == branch]
    if not records:
        return 0
    print("📜 历史记录：")
    for i, r in enumerate(records, 1):
        status = "✅" if r.get("success", True) else "❌"
        review = f" | review={r['code_review_id']}" if r.get("code_review_id") else ""
        print(f"  {i}. [{r['ts']}] {status} {r['app']}/{r['branch']} "
              f"| {r['req_id']} | {r['story']}{review}")
    print()
    return len(records)


def _save(records):
    path = _history_path()
    path.parent.mkdir(parents=True, exist_ok=True)
    lines = [json.dumps(r, ensure_ascii=False) for r in records]
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def main():
    """独立调用：python history.py [app] [branch]"""
    app = sys.argv[1] if len(sys.argv) > 1 else None
    branch = sys.argv[2] if len(sys.argv) > 2 else None
    count = show_history(app, branch)
    if count == 0:
        print("暂无历史记录")


if __name__ == "__main__":
    main()
