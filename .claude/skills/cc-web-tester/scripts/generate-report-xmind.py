#!/usr/bin/env python3
"""
从测试报告 JSON 生成带执行结果标注的 .xmind 文件。

用法:
  python3 generate-report-xmind.py <input.json> <output.xmind>

输入 JSON 格式（在测试用例 JSON 基础上，每条 case 追加 result 和 remark）:
{
  "title": "网站名称 测试报告",
  "url": "https://example.com",
  "date": "2026-03-05",
  "summary": {"total": 20, "passed": 18, "failed": 1, "blocked": 1, "skipped": 0},
  "modules": [
    {
      "name": "模块名称",
      "patterns": ["Create", "Read", "Delete"],
      "cases": [
        {
          "id": "TC-001",
          "title": "用例标题",
          "priority": "P0",
          "result": "通过",
          "remark": ""
        }
      ]
    }
  ]
}

注: patterns 为工作流必须字段，脚本层面做了兼容处理（缺失时不报错）。
"""

import json
import sys

from xmind_common import gen_id, make_topic, build_module_title, write_xmind


RESULT_MARKERS = {
    "通过": "✅",
    "失败": "❌",
    "阻塞": "⚠️",
    "跳过": "⏭️",
}


def build_xmind_content(data: dict) -> list:
    root_id = gen_id("report-root")
    summary = data.get("summary", {})

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
            # 统计该优先级的通过数
            passed = sum(1 for c in cases if c.get("result") == "通过")
            case_topics = []
            for case in cases:
                result = case.get("result", "跳过")
                marker = RESULT_MARKERS.get(result, "")
                remark = case.get("remark", "")

                # 构造 notes（仅失败/阻塞时追加详情）
                notes_lines = []
                if result in ("失败", "阻塞") and remark:
                    notes_lines.append(f"实际结果: {remark}")
                    if case.get("screenshot"):
                        notes_lines.append(f"截图: {case['screenshot']}")

                case_topic = make_topic(
                    title=f"{case['id']}: {case['title']} {marker}",
                    topic_id=gen_id(f"report-{case['id']}"),
                    labels=[case["priority"], result],
                    notes="\n".join(notes_lines) if notes_lines else None,
                )
                case_topics.append(case_topic)

            priority_topic = make_topic(
                title=f"{priority} ({passed}/{len(cases)})",
                topic_id=gen_id(f"report-{module['name']}-{priority}"),
                children=case_topics,
            )
            priority_topics.append(priority_topic)

        module_topic = make_topic(
            title=build_module_title(module["name"], module.get("patterns", [])),
            topic_id=gen_id(f"report-{module['name']}"),
            children=priority_topics,
        )
        module_topics.append(module_topic)

    # 根节点标题含汇总
    summary_label = (
        f"通过:{summary.get('passed',0)} "
        f"失败:{summary.get('failed',0)} "
        f"阻塞:{summary.get('blocked',0)} "
        f"跳过:{summary.get('skipped',0)}"
    )
    root_topic = make_topic(
        title=data["title"],
        topic_id=root_id,
        children=module_topics,
        labels=[data.get("url", ""), data.get("date", ""), summary_label],
    )
    root_topic["structureClass"] = "org.xmind.ui.logic.right"

    sheet = {
        "id": gen_id("report-sheet"),
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
    if "summary" not in data:
        print("错误: JSON 缺少 'summary' 字段", file=sys.stderr)
        sys.exit(1)
    if "total" not in data["summary"]:
        print("错误: summary 缺少 'total' 字段", file=sys.stderr)
        sys.exit(1)
    if "modules" not in data or not isinstance(data.get("modules"), list):
        print("错误: JSON 缺少 'modules' 字段或其值不是列表", file=sys.stderr)
        sys.exit(1)

    content = build_xmind_content(data)
    write_xmind(content, output_path)
    print(f"已生成: {output_path}")


if __name__ == "__main__":
    main()
