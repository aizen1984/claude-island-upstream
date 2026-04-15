"""
xmind 生成公共函数：gen_id、make_topic、write_xmind。

被 generate-xmind.py 和 generate-report-xmind.py 共同使用。
"""

import hashlib
import json
import zipfile


def gen_id(seed: str) -> str:
    """生成稳定的唯一 ID（基于 MD5 前 24 位）。"""
    return hashlib.md5(seed.encode()).hexdigest()[:24]


def make_topic(title: str, topic_id: str, children=None, labels=None, notes=None):
    """构造 xmind content.json 中的 topic 节点。"""
    topic = {
        "id": topic_id,
        "class": "topic",
        "title": title,
    }
    if labels:
        topic["labels"] = labels
    if notes:
        topic["notes"] = {"plain": {"content": notes}}
    if children:
        topic["children"] = {"attached": children}
    return topic


def build_module_title(name: str, patterns: list) -> str:
    """构造模块标题：如有 patterns 字段，追加模式标签。"""
    if patterns:
        tags = ",".join(f"[{p}]" for p in patterns)
        return f"{name} {tags}"
    return name


def write_xmind(content: list, output_path: str):
    """将 content 写入 .xmind 文件（ZIP 格式，兼容 XMind Zen/2020+）。"""
    metadata = {
        "creator": {
            "name": "claude-web-functional-tester",
        },
    }

    manifest = {
        "file-entries": {
            "content.json": {},
            "metadata.json": {},
        },
    }

    with zipfile.ZipFile(output_path, "w", zipfile.ZIP_DEFLATED) as zf:
        zf.writestr("content.json", json.dumps(content, ensure_ascii=False, indent=2))
        zf.writestr("metadata.json", json.dumps(metadata, ensure_ascii=False, indent=2))
        zf.writestr("manifest.json", json.dumps(manifest, ensure_ascii=False, indent=2))
