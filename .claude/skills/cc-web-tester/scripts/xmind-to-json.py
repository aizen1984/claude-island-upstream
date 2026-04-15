#!/usr/bin/env python3
"""
从 .xmind 文件反向解析为测试用例 JSON。

用法:
  python3 xmind-to-json.py <input.xmind> <output.json>

输出 JSON 格式与 generate-xmind.py 的输入格式一致，可直接用于重新生成 xmind 或转换为 md。

如果 output.json 已存在（即 Phase 2 生成的原始 JSON），会自动合并 xmind 中不存储的字段
（pattern、data_lifecycle、patterns），避免反向同步时丢失。
"""

import json
import os
import sys
import zipfile
import re


def parse_case_topic(topic: dict) -> dict:
    """从用例级 topic 解析出一条测试用例。"""
    title_raw = topic.get("title", "")

    # 解析 "TC-001: 用例标题" 格式
    match = re.match(r"(TC-\d+):\s*(.*)", title_raw)
    if match:
        case_id = match.group(1)
        case_title = match.group(2)
    else:
        case_id = ""
        case_title = title_raw

    # 从 labels 提取优先级
    labels = topic.get("labels", [])
    priority = ""
    for label in labels:
        if re.match(r"P\d", label):
            priority = label
            break

    # 从 notes 解析前置条件、步骤、预期结果
    precondition = ""
    steps = []
    expected = ""

    notes_text = ""
    notes = topic.get("notes", {})
    if isinstance(notes, dict):
        plain = notes.get("plain", {})
        if isinstance(plain, dict):
            notes_text = plain.get("content", "")
        elif isinstance(plain, str):
            notes_text = plain

    if notes_text:
        lines = notes_text.strip().split("\n")
        current_section = None
        for line in lines:
            stripped = line.strip()
            if stripped.startswith("前置条件:") or stripped.startswith("前置条件："):
                precondition = stripped.split(":", 1)[-1].split("：", 1)[-1].strip()
                current_section = None
            elif stripped.startswith("操作步骤:") or stripped.startswith("操作步骤："):
                current_section = "steps"
            elif stripped.startswith("预期结果:") or stripped.startswith("预期结果："):
                expected = stripped.split(":", 1)[-1].split("：", 1)[-1].strip()
                current_section = None
            elif current_section == "steps":
                # 去掉序号前缀 "1. " "2. " 等
                step = re.sub(r"^\d+\.\s*", "", stripped)
                if step:
                    steps.append(step)

    return {
        "id": case_id,
        "title": case_title,
        "priority": priority,
        "precondition": precondition,
        "steps": steps,
        "expected": expected,
    }


def parse_xmind(xmind_path: str) -> dict:
    """解析 .xmind 文件为测试用例 JSON 结构。"""
    with zipfile.ZipFile(xmind_path, "r") as zf:
        if "content.json" not in zf.namelist():
            print("错误: xmind 文件中找不到 content.json", file=sys.stderr)
            sys.exit(1)
        try:
            content = json.loads(zf.read("content.json"))
        except json.JSONDecodeError as e:
            print(f"错误: content.json 解析失败: {e}", file=sys.stderr)
            sys.exit(1)

    if not isinstance(content, list) or len(content) == 0:
        print("错误: content.json 格式无效，期望非空数组", file=sys.stderr)
        sys.exit(1)

    sheet = content[0]
    if "rootTopic" not in sheet:
        print("错误: content.json 中缺少 rootTopic", file=sys.stderr)
        sys.exit(1)

    root = sheet["rootTopic"]

    # 从 root labels 提取 url 和 date
    labels = root.get("labels", [])
    url = labels[0] if len(labels) > 0 else ""
    date = labels[1] if len(labels) > 1 else ""

    result = {
        "title": root.get("title", ""),
        "url": url,
        "date": date,
        "modules": [],
    }

    # 遍历模块（root 的直接子节点）
    module_topics = root.get("children", {}).get("attached", [])
    for module_topic in module_topics:
        # 模块标题可能含 patterns 标签后缀，如 "模块名 [Create],[Read]"，需去掉
        raw_title = module_topic.get("title", "")
        module_name = re.sub(r"\s+\[[\w]+\](?:,\[[\w]+\])*$", "", raw_title).strip()
        module = {
            "name": module_name or raw_title,
            "cases": [],
        }

        # 先分类模块的子节点
        all_children = module_topic.get("children", {}).get("attached", [])
        priority_groups = []  # 匹配 P\d 的节点（优先级分组）
        direct_cases = []     # 不匹配 P\d 但包含 TC- 的节点（直接用例）

        for topic in all_children:
            title = topic.get("title", "")
            if re.match(r"P\d", title):
                priority_groups.append(topic)
            elif "TC-" in title:
                direct_cases.append(topic)

        # 处理优先级分组下的用例
        for priority_topic in priority_groups:
            priority_match = re.match(r"(P\d)", priority_topic.get("title", ""))
            fallback_priority = priority_match.group(1) if priority_match else ""

            case_topics = priority_topic.get("children", {}).get("attached", [])
            for case_topic in case_topics:
                case = parse_case_topic(case_topic)
                if not case["priority"] and fallback_priority:
                    case["priority"] = fallback_priority
                module["cases"].append(case)

        # 处理直接挂在模块下的用例（跳过优先级分组层）
        for child in direct_cases:
            case = parse_case_topic(child)
            module["cases"].append(case)

        result["modules"].append(module)

    return result


def merge_from_original(data: dict, original_path: str) -> dict:
    """从原始 JSON 合并 xmind 中不存储的字段（pattern、data_lifecycle、patterns）。"""
    if not os.path.exists(original_path):
        return data

    try:
        with open(original_path, "r", encoding="utf-8") as f:
            original = json.load(f)
    except (json.JSONDecodeError, OSError):
        return data

    # 构建原始数据索引：module name → {patterns, case_id → case_extra_fields}
    orig_modules = {}
    for module in original.get("modules", []):
        case_index = {}
        for case in module.get("cases", []):
            extra = {}
            if "pattern" in case:
                extra["pattern"] = case["pattern"]
            if "data_lifecycle" in case:
                extra["data_lifecycle"] = case["data_lifecycle"]
            if extra:
                case_index[case["id"]] = extra
        orig_modules[module["name"]] = {
            "patterns": module.get("patterns", []),
            "cases": case_index,
        }

    merged_count = 0
    for module in data["modules"]:
        orig = orig_modules.get(module["name"])
        if not orig:
            print(f"警告: 模块 '{module['name']}' 在原始 JSON 中未找到匹配，跳过字段合并", file=sys.stderr)
            continue
        if orig["patterns"] and "patterns" not in module:
            module["patterns"] = orig["patterns"]
            merged_count += 1
        for case in module["cases"]:
            case_extra = orig["cases"].get(case["id"])
            if not case_extra:
                continue
            for key, value in case_extra.items():
                if key not in case:
                    case[key] = value
                    merged_count += 1

    if merged_count > 0:
        print(f"已从原始 JSON 合并 {merged_count} 个字段（pattern/data_lifecycle/patterns）")

    return data


def main():
    if len(sys.argv) != 3:
        print(f"用法: {sys.argv[0]} <input.xmind> <output.json>", file=sys.stderr)
        sys.exit(1)

    xmind_path = sys.argv[1]
    output_path = sys.argv[2]

    data = parse_xmind(xmind_path)

    # 如果输出路径已存在原始 JSON，合并 xmind 中不存储的字段
    data = merge_from_original(data, output_path)

    with open(output_path, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)

    total_cases = sum(len(m["cases"]) for m in data["modules"])
    print(f"已解析: {len(data['modules'])} 个模块, {total_cases} 条用例 → {output_path}")


if __name__ == "__main__":
    main()
