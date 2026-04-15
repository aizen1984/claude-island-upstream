#!/usr/bin/env python3
"""
从测试用例 JSON 生成测试用例.md 文档。

用法:
  python3 json-to-md.py <input.json> <output.md>

输入 JSON 格式与 generate-xmind.py / xmind-to-json.py 一致。
"""

import json
import sys
from collections import Counter


def generate_md(data: dict) -> str:
    """将测试用例 JSON 转换为 Markdown 文档。"""
    lines = []

    lines.append(f"# {data['title']}")
    lines.append("")
    lines.append("## 基本信息")
    lines.append("")
    lines.append("| 项目 | 内容 |")
    lines.append("|------|------|")
    lines.append(f"| 目标 URL | {data.get('url', '')} |")
    lines.append(f"| 生成时间 | {data.get('date', '')} |")
    lines.append("| 基于文档 | 功能分析报告.md |")
    lines.append("")

    # 统计
    all_cases = []
    for module in data["modules"]:
        all_cases.extend(module["cases"])

    priority_count = Counter(c["priority"] for c in all_cases)
    lines.append("## 统计")
    lines.append("")
    lines.append(f"- **总用例数**: {len(all_cases)}")
    parts = []
    for p in ["P0", "P1", "P2", "P3"]:
        if priority_count.get(p, 0) > 0:
            parts.append(f"{p}: {priority_count[p]}")
    lines.append(f"- {' | '.join(parts)}")
    lines.append("")

    # 用例清单
    lines.append("## 用例清单")
    lines.append("")

    for module in data["modules"]:
        if module["cases"]:
            lines.append(f"\n## {module['name']}\n")
            lines.append("")

        for case in module["cases"]:
            case_id = case.get("id", "TC-???")
            title = case.get("title", "")
            lines.append(f"### {case_id}: {title}")
            lines.append("")
            lines.append(f"- **优先级**: {case.get('priority', '')}")

            if case.get("precondition"):
                lines.append(f"- **前置条件**: {case['precondition']}")

            if case.get("steps"):
                lines.append("- **操作步骤**:")
                for i, step in enumerate(case["steps"], 1):
                    lines.append(f"  {i}. {step}")

            if case.get("expected"):
                lines.append(f"- **预期结果**: {case['expected']}")

            lines.append("")

    return "\n".join(lines)


def main():
    if len(sys.argv) != 3:
        print(f"用法: {sys.argv[0]} <input.json> <output.md>", file=sys.stderr)
        sys.exit(1)

    input_path = sys.argv[1]
    output_path = sys.argv[2]

    with open(input_path, "r", encoding="utf-8") as f:
        data = json.load(f)

    # 输入验证
    if "modules" not in data or not isinstance(data.get("modules"), list):
        print("错误: JSON 缺少 'modules' 字段或其值不是列表", file=sys.stderr)
        sys.exit(1)

    md_content = generate_md(data)

    with open(output_path, "w", encoding="utf-8") as f:
        f.write(md_content)

    total = sum(len(m["cases"]) for m in data["modules"])
    print(f"已生成: {total} 条用例 → {output_path}")


if __name__ == "__main__":
    main()
