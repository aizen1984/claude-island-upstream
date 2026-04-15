#!/usr/bin/env python3
"""
从测试用例 JSON 生成 .xmind 文件。

用法:
  python3 generate-xmind.py <input.json> <output.xmind>

输入 JSON 格式:
{
  "title": "网站名称 测试用例",
  "url": "https://example.com",
  "date": "2026-03-05",
  "modules": [
    {
      "name": "模块名称",
      "patterns": ["Create", "Read", "Delete"],
      "cases": [
        {
          "id": "TC-001",
          "title": "用例标题",
          "priority": "P0",
          "pattern": "Create",
          "precondition": "前置条件",
          "steps": ["步骤1", "步骤2"],
          "expected": "预期结果",
          "data_lifecycle": {
            "creates": "实体名或null",
            "depends": "TC-XXX或null",
            "consumes": "TC-XXX或null"
          }
        }
      ]
    }
  ]
}

注: patterns/pattern/data_lifecycle 为工作流必须字段（无关联时填 null），
脚本层面做了兼容处理（缺失时不报错）。
"""

import json
import sys

from xmind_common import gen_id, make_topic, build_module_title, write_xmind


def build_xmind_content(data: dict) -> list:
    """将测试用例数据构建为 xmind content.json 结构。"""
    root_id = gen_id("root")

    module_topics = []
    for module in data["modules"]:
        # 按优先级分组
        priority_groups = {}
        for case in module["cases"]:
            p = case["priority"]
            if p not in priority_groups:
                priority_groups[p] = []
            priority_groups[p].append(case)

        priority_topics = []
        for priority in sorted(priority_groups.keys()):
            cases = priority_groups[priority]
            case_topics = []
            for case in cases:
                # 用例节点：步骤和预期结果放 notes
                notes_lines = []
                if case.get("precondition"):
                    notes_lines.append(f"前置条件: {case['precondition']}")
                if case.get("steps"):
                    notes_lines.append("操作步骤:")
                    for i, step in enumerate(case["steps"], 1):
                        notes_lines.append(f"  {i}. {step}")
                if case.get("expected"):
                    notes_lines.append(f"预期结果: {case['expected']}")

                case_topic = make_topic(
                    title=f"{case['id']}: {case['title']}",
                    topic_id=gen_id(case["id"]),
                    labels=[case["priority"]],
                    notes="\n".join(notes_lines) if notes_lines else None,
                )
                case_topics.append(case_topic)

            priority_topic = make_topic(
                title=f"{priority} ({len(cases)})",
                topic_id=gen_id(f"{module['name']}-{priority}"),
                children=case_topics,
            )
            priority_topics.append(priority_topic)

        module_topic = make_topic(
            title=build_module_title(module["name"], module.get("patterns", [])),
            topic_id=gen_id(module["name"]),
            children=priority_topics,
        )
        module_topics.append(module_topic)

    root_topic = make_topic(
        title=data["title"],
        topic_id=root_id,
        children=module_topics,
        labels=[data.get("url", ""), data.get("date", "")],
    )
    root_topic["structureClass"] = "org.xmind.ui.logic.right"

    sheet = {
        "id": gen_id("sheet"),
        "class": "sheet",
        "title": data["title"],
        "rootTopic": root_topic,
    }
    return [sheet]


def main():
    if len(sys.argv) != 3:
        print(f"用法: {sys.argv[0]} <input.json> <output.xmind>", file=sys.stderr)
        sys.exit(1)

    input_path = sys.argv[1]
    output_path = sys.argv[2]

    with open(input_path, "r", encoding="utf-8") as f:
        data = json.load(f)

    # 输入验证
    if "modules" not in data or not isinstance(data.get("modules"), list):
        print("错误: JSON 缺少 'modules' 字段或其值不是列表", file=sys.stderr)
        sys.exit(1)
    for i, module in enumerate(data["modules"]):
        if "name" not in module:
            print(f"错误: modules[{i}] 缺少 'name' 字段", file=sys.stderr)
            sys.exit(1)
        if "cases" not in module:
            print(f"错误: modules[{i}] ('{module['name']}') 缺少 'cases' 字段", file=sys.stderr)
            sys.exit(1)

    content = build_xmind_content(data)
    write_xmind(content, output_path)
    print(f"已生成: {output_path}")


if __name__ == "__main__":
    main()
