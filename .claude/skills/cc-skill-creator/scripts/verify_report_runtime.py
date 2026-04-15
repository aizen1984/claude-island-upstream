#!/usr/bin/env python3
"""
verify_report_runtime.py — Iter 23

数据报告运行时校验器（HumanLayer back-pressure 模式 + Anthropic quote grounding）。

与 check_consistency.py 的区别:
  - check_consistency.py: 静态文档 lint（pre-commit），拦截已知漂移模式
  - verify_report_runtime.py: 运行时报告校验（post-generation），拦截 agent 动态生成时的 fabrication / under-reporting

支持的 quote 形式:
  - <quote file="path" line="42">原文</quote>           — 标签式（默认）
  - <quote file="path" line="42-48">原文</quote>        — 多行
  - <evidence type="..." path="..."/>                    — cc-web-tester 等效形式

退出码（HumanLayer back-pressure 协议）:
  - 0: 静默通过（success silent）
  - 2: 失败 + stderr 详细错误（触发 agent 自动修复，failure verbose）

使用:
  python verify_report_runtime.py REPORT.md \\
    --base-dir /path/to/source/files \\
    --patterns "pattern1" "pattern2"

设计依据:
  - Anthropic minimizing-hallucinations: quote grounding + citation verification
  - HumanLayer harness engineering: back-pressure success-silent failure-verbose
  - Iter 17 教训: 负向测试必须真实注入，lint 跑绿不代表防线有效
"""

import re
import sys
import argparse
import subprocess
from pathlib import Path

# Quote 标签正则 — 支持单行和多行 (line="42" or line="42-48")
QUOTE_TAG = re.compile(
    r'<quote\s+file="([^"]+)"\s+line="(\d+)(?:-(\d+))?"[^>]*>([^<]*)</quote>'
)

# Evidence 标签正则（cc-web-tester 等效形式）
EVIDENCE_TAG = re.compile(
    r'<evidence\s+type="([^"]+)"\s+path="([^"]+)"\s*/?>'
)

# 跳过模板占位符的启发式
PLACEHOLDER_PATTERNS = [
    "原文", "代码原文", "原文字符", "原文字符逐字", "代码原文",
    "原文片段", "原文片段]", "...", "[原文]", "关键代码片段"
]


def is_placeholder(text: str) -> bool:
    """判断 quote 内容是否模板占位符（应跳过验证）"""
    text = text.strip()
    if not text:
        return True
    if text in PLACEHOLDER_PATTERNS:
        return True
    if text.startswith("[") and text.endswith("]"):
        return True
    if text.startswith("{") and text.endswith("}"):
        return True
    if text.startswith("```") or text.endswith("```"):
        return True
    return False


def verify_no_fabrication(report_text: str, base_dir: Path) -> list[dict]:
    """
    对每个 <quote> 标签反向 grep 验证原文存在 + 行号校验。

    校验项:
    1. file 字段对应的文件存在
    2. quote 内容在文件中存在（grep -F 字面匹配）
    3. line 字段声明的行号区间真的包含 quote 内容（防"对内容 + 错行号"）

    返回: fabrication 错误列表（空表示通过）

    Note: line 校验对多行 quote 仅检查 line_start 是否在 grep 命中行号 ±2 容差内
          （多行 quote 的 grep -F 把每行作为独立 pattern，grep 返回每行的真实行号）
    """
    errors = []
    for m in QUOTE_TAG.finditer(report_text):
        file_path = m.group(1)
        line_start = m.group(2)
        line_end = m.group(3)
        quoted_text = m.group(4).strip()

        if is_placeholder(quoted_text):
            continue

        full_path = base_dir / file_path
        if not full_path.exists():
            errors.append({
                "type": "FABRICATED_FILE",
                "file": file_path,
                "line": line_start,
                "quote_preview": quoted_text[:80],
                "reason": f"文件不存在: {full_path}"
            })
            continue

        # 用 grep 验证原文存在（grep -F 字面匹配，避免正则转义问题）
        try:
            result = subprocess.run(
                ["grep", "-Fn", quoted_text, str(full_path)],
                capture_output=True, text=True, timeout=10
            )
            if result.returncode != 0:
                errors.append({
                    "type": "FABRICATED_QUOTE",
                    "file": file_path,
                    "line": line_start,
                    "quote_preview": quoted_text[:80],
                    "reason": "原文在文件中不存在（瞎编/改写/错误引用）"
                })
                continue

            # 行号校验: 解析 grep 输出的实际行号集合
            actual_lines = set()
            for output_line in result.stdout.strip().split("\n"):
                if ":" in output_line:
                    try:
                        actual_lines.add(int(output_line.split(":", 1)[0]))
                    except ValueError:
                        continue

            if actual_lines:
                declared_start = int(line_start)
                declared_end = int(line_end) if line_end else declared_start
                declared_range = set(range(declared_start, declared_end + 1))

                # 容差: declared_start 必须在某个 actual_line 的 ±2 内
                # （多行 quote 的 grep 会返回每行行号，line_start 应该匹配第一行）
                in_range = bool(declared_range & actual_lines)
                near_range = any(
                    abs(d - a) <= 2 for d in declared_range for a in actual_lines
                )
                if not in_range and not near_range:
                    errors.append({
                        "type": "WRONG_LINE_NUMBER",
                        "file": file_path,
                        "declared_line": line_start + (f"-{line_end}" if line_end else ""),
                        "actual_lines": sorted(actual_lines)[:5],
                        "quote_preview": quoted_text[:80],
                        "reason": f"声明 line={line_start}{'~'+line_end if line_end else ''} 但 quote 内容实际在 {sorted(actual_lines)[:3]} 行"
                    })
        except subprocess.TimeoutExpired:
            errors.append({
                "type": "GREP_TIMEOUT",
                "file": file_path,
                "quote_preview": quoted_text[:80],
                "reason": "grep 超时（文件过大?）"
            })
    return errors


def verify_no_underreport(
    report_text: str,
    base_dir: Path,
    patterns: list[str],
    file_glob: str = "*.md",
    report_path: Path | None = None
) -> list[dict]:
    """
    对每个 pattern 在 base_dir 下搜索，检查报告是否完整覆盖所有命中。

    返回: under-report 错误列表（空表示通过）

    Note: 自动排除 report_path 本身（避免 self-inclusion false positive：
          report 自身含 pattern 字面字符时被 grep 命中后误判为漏报）。
    """
    errors = []

    # 收集报告中提到的所有文件路径（来自 quote 标签）
    reported_files = set()
    for m in QUOTE_TAG.finditer(report_text):
        reported_files.add(m.group(1))

    # 计算报告文件相对路径（用于排除 self-inclusion）
    report_rel = None
    if report_path is not None:
        try:
            report_rel = str(report_path.resolve().relative_to(base_dir))
        except ValueError:
            report_rel = None

    for pattern in patterns:
        try:
            result = subprocess.run(
                ["grep", "-rln", "--include=" + file_glob, pattern, str(base_dir)],
                capture_output=True, text=True, timeout=30
            )
        except subprocess.TimeoutExpired:
            errors.append({
                "type": "GREP_TIMEOUT",
                "pattern": pattern,
                "reason": "活文档 grep 超时"
            })
            continue

        real_hits = set()
        if result.returncode == 0:
            for line in result.stdout.strip().split("\n"):
                if not line:
                    continue
                try:
                    rel = str(Path(line).relative_to(base_dir))
                    real_hits.add(rel)
                except ValueError:
                    real_hits.add(line)

        # 排除报告文件本身（self-inclusion false positive）
        if report_rel is not None:
            real_hits.discard(report_rel)

        if not real_hits:
            continue  # pattern 在活文档零命中，自然不会漏报

        # 找漏报: 活文档命中但报告未提及
        missed = real_hits - reported_files
        if missed:
            errors.append({
                "type": "UNDER_REPORTED",
                "pattern": pattern,
                "real_hits_count": len(real_hits),
                "reported_count": len(real_hits - missed),
                "missed_files": sorted(missed)[:10],
                "reason": f"活文档 {len(real_hits)} 处命中（已排除报告自身），报告仅引用 {len(real_hits - missed)} 处"
            })
    return errors


def verify_scan_complete(report_text: str) -> list[dict]:
    """
    检查报告是否包含 scan_complete 字段声明（数据契约要求）。
    缺失时报警告（非 error）。
    """
    if "scan_complete" not in report_text:
        return [{
            "type": "MISSING_SCAN_COMPLETE",
            "reason": "报告未声明 scan_complete 字段（data-report-protocol §三 要求）",
            "severity": "warning"
        }]
    return []


def main():
    parser = argparse.ArgumentParser(
        description="数据报告运行时校验器 (Iter 23 - data-report-protocol)"
    )
    parser.add_argument("report", help="待校验的报告文件路径")
    parser.add_argument("--base-dir", default=".", help="源文件搜索根目录（默认 CWD）")
    parser.add_argument("--patterns", nargs="*", default=[],
                        help="under-report 检测的 pattern 列表")
    parser.add_argument("--file-glob", default="*.md",
                        help="under-report 搜索的文件 glob（默认 *.md）")
    parser.add_argument("--skip-fabrication", action="store_true",
                        help="跳过 fabrication 检测")
    parser.add_argument("--skip-underreport", action="store_true",
                        help="跳过 under-report 检测")
    parser.add_argument("--skip-scan-complete", action="store_true",
                        help="跳过 scan_complete 字段检查")
    parser.add_argument("--verbose", "-v", action="store_true",
                        help="即使通过也输出详细统计")
    args = parser.parse_args()

    report_path = Path(args.report)
    if not report_path.exists():
        print(f"ERROR: 报告文件不存在: {report_path}", file=sys.stderr)
        sys.exit(2)

    report_text = report_path.read_text(encoding="utf-8")
    base_dir = Path(args.base_dir).resolve()

    all_errors = []
    all_warnings = []

    if not args.skip_fabrication:
        fab_errors = verify_no_fabrication(report_text, base_dir)
        all_errors.extend(fab_errors)

    if not args.skip_underreport and args.patterns:
        under_errors = verify_no_underreport(
            report_text, base_dir, args.patterns, args.file_glob,
            report_path=report_path
        )
        all_errors.extend(under_errors)

    if not args.skip_scan_complete:
        sc_warnings = verify_scan_complete(report_text)
        all_warnings.extend(sc_warnings)

    # 失败: stderr verbose + exit 2
    if all_errors:
        print(f"\n❌ verify_report_runtime: {len(all_errors)} 个失真错误", file=sys.stderr)
        for i, e in enumerate(all_errors, 1):
            print(f"\n  [{i}] {e['type']}: {e.get('reason', '')}", file=sys.stderr)
            for k, v in e.items():
                if k not in ("type", "reason"):
                    print(f"      {k}: {v}", file=sys.stderr)
        sys.exit(2)

    # 警告（非阻塞）
    if all_warnings:
        print(f"⚠️  {len(all_warnings)} 个警告", file=sys.stderr)
        for w in all_warnings:
            print(f"  [{w['type']}] {w['reason']}", file=sys.stderr)

    # 成功: silent or verbose
    if args.verbose:
        # 统计信息
        quote_count = len(QUOTE_TAG.findall(report_text))
        evidence_count = len(EVIDENCE_TAG.findall(report_text))
        print(f"✅ verify_report_runtime: {quote_count} 个 quote + {evidence_count} 个 evidence 全部验证通过")

    sys.exit(0)


if __name__ == "__main__":
    main()
