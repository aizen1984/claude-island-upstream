#!/usr/bin/env python3
"""
Skill 一致性校验脚本

检查 skill-rules.json 与实际 SKILL.md 目录的一致性，包括：
1. Skill 列表一致性（skills keys / priorityOrder / 实际目录）
2. 禁止组合引用一致性
3. 隐式依赖引用一致性
4. Tier 一致性
5. 数据契约引用一致性
"""

import argparse
import json
import os
import re
import sys
from pathlib import Path


def load_skill_rules(skills_dir: Path) -> dict:
    """加载 skill-rules.json"""
    rules_path = skills_dir / "skill-rules.json"
    if not rules_path.exists():
        print(f"[FATAL] skill-rules.json not found: {rules_path}")
        sys.exit(2)
    with open(rules_path, "r", encoding="utf-8") as f:
        return json.load(f)


def get_skill_dirs(skills_dir: Path) -> set:
    """获取实际存在 SKILL.md 的目录名（排除 shared-rules）"""
    dirs = set()
    for entry in skills_dir.iterdir():
        if entry.is_dir() and entry.name != "shared-rules" and (entry / "SKILL.md").exists():
            dirs.add(entry.name)
    return dirs


def check_skill_list_consistency(rules: dict, actual_dirs: set, verbose: bool) -> list:
    """校验项 1: Skill 列表一致性"""
    errors = []
    warnings = []

    skills_keys = set(rules.get("skills", {}).keys())
    priority_order = set(rules.get("priorityOrder", []))

    if verbose:
        print("\n--- Skill 列表一致性详细信息 ---")
        print(f"  skills keys:    {sorted(skills_keys)}")
        print(f"  priorityOrder:  {sorted(priority_order)}")
        print(f"  SKILL.md dirs:  {sorted(actual_dirs)}")

    # skills keys vs priorityOrder
    in_keys_not_priority = skills_keys - priority_order
    in_priority_not_keys = priority_order - skills_keys
    if in_keys_not_priority:
        errors.append(f"skills 中存在但 priorityOrder 中缺失: {sorted(in_keys_not_priority)}")
    if in_priority_not_keys:
        errors.append(f"priorityOrder 中存在但 skills 中缺失: {sorted(in_priority_not_keys)}")

    # skills keys vs actual dirs
    in_keys_not_dirs = skills_keys - actual_dirs
    in_dirs_not_keys = actual_dirs - skills_keys
    if in_keys_not_dirs:
        warnings.append(f"skills 中注册但无 SKILL.md 目录: {sorted(in_keys_not_dirs)}")
    if in_dirs_not_keys:
        warnings.append(f"SKILL.md 目录未在 skill-rules.json 中注册: {sorted(in_dirs_not_keys)}")

    # priorityOrder vs actual dirs
    in_priority_not_dirs = priority_order - actual_dirs
    in_dirs_not_priority = actual_dirs - priority_order
    if in_priority_not_dirs:
        warnings.append(f"priorityOrder 中存在但无 SKILL.md 目录: {sorted(in_priority_not_dirs)}")
    if in_dirs_not_priority:
        warnings.append(f"SKILL.md 目录未在 priorityOrder 中: {sorted(in_dirs_not_priority)}")

    return errors, warnings


def check_forbidden_combinations(rules: dict, verbose: bool) -> list:
    """校验项 2: 禁止组合一致性"""
    errors = []
    skills_keys = set(rules.get("skills", {}).keys())
    forbidden = rules.get("forbiddenCombinations", [])

    if verbose:
        print(f"\n--- 禁止组合一致性详细信息 ---")
        print(f"  禁止组合数量: {len(forbidden)}")

    for combo in forbidden:
        combo_id = combo.get("id", "<unknown>")
        from_skill = combo.get("from", "")
        to_skill = combo.get("to", "")

        if from_skill and from_skill not in skills_keys:
            errors.append(f"forbiddenCombinations[{combo_id}].from 引用了不存在的 skill: {from_skill}")
        if to_skill and to_skill not in skills_keys:
            # to 可能是阶段名（如 EXECUTE），不一定是 skill 名
            # 只在看起来像 skill 名时报错（包含 stark- 或在 skills 中）
            if to_skill.startswith("stark-") or to_skill in ["sql", "cfg", "cc-api-analyzer", "cc-skill-creator", "cc-web-tester"]:
                errors.append(f"forbiddenCombinations[{combo_id}].to 引用了不存在的 skill: {to_skill}")
            elif verbose:
                print(f"  [SKIP] forbiddenCombinations[{combo_id}].to = '{to_skill}' (非 skill 名，跳过)")

    return errors


def check_implicit_dependencies(rules: dict, verbose: bool) -> list:
    """校验项 3: 隐式依赖一致性"""
    errors = []
    skills = rules.get("skills", {})
    skills_keys = set(skills.keys())

    if verbose:
        print(f"\n--- 隐式依赖一致性详细信息 ---")

    for skill_name, skill_config in skills.items():
        deps = skill_config.get("implicitDependencies", [])
        if verbose and deps:
            print(f"  {skill_name}: {deps}")
        for dep in deps:
            if dep not in skills_keys:
                errors.append(f"{skill_name}.implicitDependencies 引用了不存在的 skill: {dep}")

    return errors


def check_tier_consistency(rules: dict, verbose: bool) -> list:
    """校验项 4: Tier 一致性"""
    errors = []
    skills = rules.get("skills", {})
    tiers = rules.get("tiers", {})
    tier_names = set(tiers.keys())

    if verbose:
        print(f"\n--- Tier 一致性详细信息 ---")
        print(f"  定义的 tiers: {sorted(tier_names)}")

    # 各 skill 的 tier 值必须在 tiers 中有定义
    for skill_name, skill_config in skills.items():
        tier = skill_config.get("tier", "")
        if tier and tier not in tier_names:
            errors.append(f"{skill_name}.tier = '{tier}' 未在 tiers 中定义")

    # tiers 中列出的 skills 应与实际 skill 的 tier 值一致
    for tier_name, tier_config in tiers.items():
        tier_skills = set(tier_config.get("skills", []))
        actual_tier_skills = {name for name, cfg in skills.items() if cfg.get("tier") == tier_name}

        in_tier_not_actual = tier_skills - actual_tier_skills
        in_actual_not_tier = actual_tier_skills - tier_skills

        if in_tier_not_actual:
            errors.append(f"tiers.{tier_name}.skills 列出了 {sorted(in_tier_not_actual)}，但这些 skill 的 tier 值并非 '{tier_name}'")
        if in_actual_not_tier:
            errors.append(f"skill {sorted(in_actual_not_tier)} 的 tier 为 '{tier_name}'，但未在 tiers.{tier_name}.skills 中列出")

        if verbose:
            print(f"  tier '{tier_name}': 声明={sorted(tier_skills)}, 实际={sorted(actual_tier_skills)}")

    return errors


def check_data_contracts(rules: dict, verbose: bool) -> list:
    """校验项 5: 数据契约一致性"""
    errors = []
    skills_keys = set(rules.get("skills", {}).keys())
    contracts = rules.get("dataContracts", {}).get("registeredContracts", [])

    if verbose:
        print(f"\n--- 数据契约一致性详细信息 ---")
        print(f"  契约数量: {len(contracts)}")

    # 从契约字符串中提取 skill 名
    # 格式如 "planner -> code-writer/work-mode" 或 "design <-> planner"
    # 需要映射简称到全名
    short_to_full = {
        "planner": "cc-planner",
        "code-writer": "cc-code-writer",
        "work-mode": "cc-work-mode",
        "code-reviewer": "cc-code-reviewer",
        "design": "cc-design",
        "cc-tdd": "cc-tdd",
    }

    for contract in contracts:
        # 提取所有可能的 skill 引用（用 -> / <- / <-> / , / / 分割）
        parts = re.split(r'\s*(?:[<>→←↔]+|/|,)\s*', contract)
        for part in parts:
            part = part.strip()
            if not part or part == "user":
                continue
            # 尝试匹配全名或简称
            full_name = short_to_full.get(part, part)
            if full_name not in skills_keys and part not in skills_keys:
                if verbose:
                    print(f"  [WARN] 契约 '{contract}' 中的 '{part}' 可能是简称，未匹配到 skill")

    return errors


def check_shared_rules_paths(skills_dir: Path, verbose: bool) -> list:
    """校验项 6: shared-rules 路径引用存在性

    防 'cc-adversarial-verification.md' 类文件名漂移：所有 cc-* skill 中引用
    `shared-rules/X.md` 时，X.md 必须真实存在于 shared-rules/ 目录。

    历史案例（Iter 3）：5 个 skill × 9 处错误引用 `cc-adversarial-verification.md`，
    实际文件名是 `adversarial-verification.md`（无 cc- 前缀）。
    """
    errors = []
    shared_rules_dir = skills_dir / "shared-rules"

    if not shared_rules_dir.exists():
        if verbose:
            print(f"\n--- shared-rules 路径引用一致性 ---")
            print(f"  [SKIP] shared-rules 目录不存在: {shared_rules_dir}")
        return errors

    # 收集实际存在的 .md 文件名
    actual_files = {f.name for f in shared_rules_dir.iterdir() if f.is_file() and f.suffix == ".md"}

    if verbose:
        print(f"\n--- shared-rules 路径引用一致性详细信息 ---")
        print(f"  实际文件 ({len(actual_files)}): {sorted(actual_files)}")

    # 引用模式：shared-rules/X.md
    ref_pattern = re.compile(r'shared-rules/([a-zA-Z0-9_-]+\.md)')

    scanned_count = 0
    for skill_dir in skills_dir.iterdir():
        if not skill_dir.is_dir():
            continue
        # 跳过非 cc-* 目录（reviews/scripts/shared-rules 等）
        if not skill_dir.name.startswith("cc-"):
            continue

        for md_file in skill_dir.rglob("*.md"):
            try:
                content = md_file.read_text(encoding="utf-8")
            except Exception:
                continue
            scanned_count += 1

            for match in ref_pattern.finditer(content):
                referenced = match.group(1)
                if referenced not in actual_files:
                    rel_path = md_file.relative_to(skills_dir)
                    line_no = content[:match.start()].count('\n') + 1
                    errors.append(
                        f"{rel_path}:{line_no} 引用了不存在的 `shared-rules/{referenced}` "
                        f"(实际存在: {sorted(actual_files)})"
                    )

    if verbose:
        print(f"  扫描文件数: {scanned_count}")

    return errors


def check_orchestration_chapter_refs(skills_dir: Path, verbose: bool) -> list:
    """校验项 7: skill-orchestration.md 章节号反向引用一致性

    防 '第六章' 类悬空引用：所有 cc-* skill 中引用 skill-orchestration.md 的
    `第 N 章` 或 `§N`，N 必须是 orchestration 实际存在的章节号。

    历史案例（Iter 2）：cc-think-first 是传染源（4 处误用 §六），传染给
    cc-planner/cc-work-mode/cc-design/cc-code-writer/cc-code-reviewer/cc-skill-creator
    共 6 个下游，合计 13 处错引。

    Iter 28 更新：skill-orchestration.md 重排，现共 7 章，§七 是预思考协议
    （原 §五 改为'可观测性'）。本规则当前只匹配 ``§N``/``第N章`` 中数字与
    实际章节数的硬上下界，未做"章节名 vs 章节号"映射校验——这是已知盲区，
    cc-think-first/cc-planner 等下游引用 ``§五 预思考`` 在 Iter 28 经独立
    复核才发现，详见 审计报告/Skills全量评审-2026-04-11/。
    """
    errors = []
    orchestration_path = skills_dir / "shared-rules" / "skill-orchestration.md"

    if not orchestration_path.exists():
        if verbose:
            print(f"\n--- skill-orchestration 章节引用一致性 ---")
            print(f"  [SKIP] skill-orchestration.md 不存在")
        return errors

    try:
        content = orchestration_path.read_text(encoding="utf-8")
    except Exception:
        return errors

    # 解析章节标题：## 零、xxx / ## 一、xxx / ## 二、xxx ... 或 ## 1、 / ## 2、
    # Iter 28 v3: capture 章节标题（用于章节名 vs 章节号的对账）
    chapter_pattern = re.compile(r'^##\s+([零一二三四五六七八九十\d]+)[、.]\s*(.*?)\s*$', re.MULTILINE)
    actual_chapters = {}  # chapter_num -> chapter_title
    for match in chapter_pattern.finditer(content):
        actual_chapters[match.group(1)] = match.group(2).strip()

    if verbose:
        print(f"\n--- skill-orchestration 章节引用一致性详细信息 ---")
        print(f"  实际章节 ({len(actual_chapters)}): {dict(sorted(actual_chapters.items()))}")

    if not actual_chapters:
        return errors  # 解析不到章节，跳过

    # 引用模式：skill-orchestration.md ... 第 N 章 / §N [可选章节名]
    # 注意：N 可能是中文数字或阿拉伯数字
    # Iter 28 修正 v3：
    #   v1 (修反引号盲区): 去掉反引号排除 + 去掉"第/§"提前排除
    #   v2 (修跨 .md 误匹配): 字符类再加上"句号"排除——避免 lazy 量词跨过另一个 .md
    #   v3 (加章节名对账): 额外 capture 章节号后面 2-15 个汉字，与 actual_chapters
    #   的 title 对账。真实 case: cc-think-first/cc-planner 等引用 "§五 预思考协议"
    #   但实际 §五 是 "可观测性"，Iter 28 独立 fresh-context evaluator 才发现
    ref_pattern = re.compile(
        r'skill-orchestration\.md[^\n.]{0,80}?(?:第([零一二三四五六七八九十\d]+)章|§([零一二三四五六七八九十\d]+))\s*([\u4e00-\u9fa5]{2,15})?'
    )

    scanned_count = 0
    for skill_dir in skills_dir.iterdir():
        if not skill_dir.is_dir() or not skill_dir.name.startswith("cc-"):
            continue

        for md_file in skill_dir.rglob("*.md"):
            try:
                file_content = md_file.read_text(encoding="utf-8")
            except Exception:
                continue
            scanned_count += 1

            for match in ref_pattern.finditer(file_content):
                chapter = match.group(1) or match.group(2)
                ref_title = (match.group(3) or "").strip()

                if chapter not in actual_chapters:
                    rel_path = md_file.relative_to(skills_dir)
                    line_no = file_content[:match.start()].count('\n') + 1
                    errors.append(
                        f"{rel_path}:{line_no} 引用 skill-orchestration.md "
                        f"第{chapter}章/§{chapter}，但实际章节为 {sorted(actual_chapters.keys())}"
                    )
                elif ref_title:
                    # v3 章节名对账：至少有一个 2 字子串重叠
                    actual_title = actual_chapters[chapter]
                    has_overlap = any(
                        ref_title[i:i + 2] in actual_title
                        for i in range(max(1, len(ref_title) - 1))
                    )
                    if not has_overlap:
                        rel_path = md_file.relative_to(skills_dir)
                        line_no = file_content[:match.start()].count('\n') + 1
                        errors.append(
                            f"{rel_path}:{line_no} 引用 skill-orchestration.md "
                            f"第{chapter}章/§{chapter} '{ref_title}'，但实际章节 "
                            f"{chapter} 标题为 '{actual_title}'（章节名不匹配）"
                        )

    if verbose:
        print(f"  扫描文件数: {scanned_count}")

    return errors


def check_intra_skill_step_refs(skills_dir: Path, verbose: bool) -> list:
    """校验项 9B: 同 skill 内部步骤号引用一致性

    防 Iter 13 类 '步骤 1.8' 副本漂移：同 skill 的 SKILL.md/prompts.md 引用
    '步骤 X.Y'，workflows*.md 必须实际定义过该步骤号。

    历史案例（Iter 13）: cc-code-writer prompts.md:62 + workflows.md:295 都写
    `步骤 1.8 注入/生成`，但 workflows.md 实际定义是 `### 步骤 1.2：验收清单预审`，
    步骤 1.8 在 skill 内根本不存在，是作者拷贝旧版未统一编号的残留。
    """
    errors = []
    # 步骤定义模式（三种都收，覆盖主流文档约定）：
    #   1. `### 步骤 X.Y` / `#### 步骤 X.Y.Z`（显式"步骤"前缀的标题）
    #   2. `#### X.Y` / `##### X.Y.Z`（纯数字子标题，必须含点）
    #   3. `3.5 xxx` / `  3.6 xxx`（正文/代码块内的编号列表子步骤，含点）
    #      用于匹配 BFS/DFS 等流程的 numbered list items
    step_def_explicit = re.compile(
        r'^#{2,5}\s*步骤\s*(\d+(?:\.\d+)+)', re.MULTILINE
    )
    step_def_numeric_heading = re.compile(
        r'^#{3,5}\s+(\d+(?:\.\d+)+)(?=\s+\S)', re.MULTILINE
    )
    # 正文编号列表：行首 0-3 空格 + X.Y[.Z] + 空格 + 非数字非点的描述字符
    # 避免误匹配 version 字符串（如 "1.2.3 release" 少见但可容忍）
    step_def_numeric_list = re.compile(
        r'^[ \t]{0,3}(\d+(?:\.\d+)+)[ \t]+(?=[^\d.\n])', re.MULTILINE
    )
    # 步骤引用模式：`步骤 X.Y`，要求 X.Y 格式（至少有一个点）
    step_ref_pattern = re.compile(r'步骤\s*(\d+(?:\.\d+)+)(?![\d\.])')

    def _is_step_valid(step: str, actual: set) -> bool:
        """层级兜底：引用 X.Y.Z 时若父级 X.Y 存在也视为合法（子级引用）。"""
        if step in actual:
            return True
        parts = step.split(".")
        # 向上回退检查父级是否存在（例 1.5.1 → 1.5）
        while len(parts) > 2:
            parts = parts[:-1]
            if ".".join(parts) in actual:
                return True
        return False

    scanned_skills = 0
    for skill_dir in sorted(skills_dir.iterdir()):
        if not skill_dir.is_dir() or not skill_dir.name.startswith("cc-"):
            continue

        # Step 1: 扫同 skill 的所有 .md 文件，收集实际定义的步骤号（联合集合）
        actual_steps = set()
        skill_md_files = list(skill_dir.rglob("*.md"))
        for md_file in skill_md_files:
            try:
                content = md_file.read_text(encoding="utf-8")
                # 三种定义都收
                for m in step_def_explicit.finditer(content):
                    actual_steps.add(m.group(1))
                for m in step_def_numeric_heading.finditer(content):
                    actual_steps.add(m.group(1))
                for m in step_def_numeric_list.finditer(content):
                    actual_steps.add(m.group(1))
            except Exception:
                continue

        if not actual_steps:
            continue  # 该 skill 无带点的步骤定义，跳过（纯数字步骤如"步骤 1/2/3"不在本规则管辖）

        scanned_skills += 1

        # Step 2: 扫所有 .md 查找引用，对照实际集合（含层级兜底）
        for md_file in skill_md_files:
            try:
                content = md_file.read_text(encoding="utf-8")
            except Exception:
                continue

            for m in step_ref_pattern.finditer(content):
                step = m.group(1)
                if not _is_step_valid(step, actual_steps):
                    rel_path = md_file.relative_to(skills_dir)
                    line_no = content[: m.start()].count("\n") + 1
                    # 显示最多 10 个实际步骤号作为参考
                    actual_sample = sorted(actual_steps)[:10]
                    errors.append(
                        f"{rel_path}:{line_no} 引用 '步骤 {step}'，"
                        f"但 skill 内实际定义的步骤号为 {actual_sample}"
                        + ("..." if len(actual_steps) > 10 else "")
                    )

    if verbose:
        print(f"\n--- 同 skill 内部步骤号引用一致性详细信息 ---")
        print(f"  扫描 skill 数（含带点步骤定义）: {scanned_skills}")

    return errors


def check_intra_skill_shared_rules_chapter_format(skills_dir: Path, verbose: bool) -> list:
    """校验项 9C: 同 skill 引用 shared-rules 章节号格式统一

    防 Iter 16 类 `S4/S5` vs `§四/§五` 混用：shared-rules 的章节用中文数字
    （`## 零、` / `## 一、` / `## 二、` ...），skill 不得用 `S\d` 前缀或
    `Section \d` 格式引用。

    历史案例（Iter 16）: cc-adversarial/SKILL.md 引用 adversarial-verification.md
    时混用 `§四`（L63 正确）和 `S4/S5`（L64/151/152/153/162 错误）共 5 处。
    Iter 3 只修了 L62 一处，漂移在 skill 内其他文件中潜伏至 Iter 16。
    """
    errors = []
    shared_dir = skills_dir / "shared-rules"
    if not shared_dir.exists():
        return errors

    shared_rules_files = {f.name for f in shared_dir.iterdir() if f.suffix == ".md"}
    if not shared_rules_files:
        return errors

    # 匹配模式：shared-rules 文件名.md 后 ≤80 字符内出现 `S\d` 或 `S\d-S\d` 或 `Section \d`
    # 注意：要求 S 后紧跟数字（避免误匹配 "SKILL.md"/"Section header" 等），
    # 并且 S 前是非字母（单词边界），避免误匹配 "TLS5" 之类
    bad_pattern = re.compile(
        r'([a-z0-9][a-z0-9-]+\.md)([^第§\n`]{0,80}?)\b(S\d+(?:-S\d+)?|Section\s+\d+)\b'
    )

    scanned_files = 0
    for skill_dir in sorted(skills_dir.iterdir()):
        if not skill_dir.is_dir() or not skill_dir.name.startswith("cc-"):
            continue

        for md_file in skill_dir.rglob("*.md"):
            try:
                content = md_file.read_text(encoding="utf-8")
            except Exception:
                continue
            scanned_files += 1

            for m in bad_pattern.finditer(content):
                ref_file = m.group(1)
                bad_ref = m.group(3)
                # 只告警真正的 shared-rules 文件引用（避免对其他 .md 文件误报）
                if ref_file in shared_rules_files:
                    rel_path = md_file.relative_to(skills_dir)
                    line_no = content[: m.start()].count("\n") + 1
                    errors.append(
                        f"{rel_path}:{line_no} 引用 {ref_file} 使用 '{bad_ref}' 格式，"
                        f"应改用中文章节号 §零/§一/§二... （shared-rules 本身用中文标题）"
                    )

    if verbose:
        print(f"\n--- 同 skill shared-rules 章节格式一致性详细信息 ---")
        print(f"  扫描文件数: {scanned_files}")
        print(f"  shared-rules 文件数: {len(shared_rules_files)}")

    return errors


def _parse_allowed_tools(frontmatter: str) -> list:
    """解析 frontmatter 的 allowed-tools 字段，返回工具条目列表。

    支持两种格式：
    1. Inline：`allowed-tools: Read, Grep, Bash(python*)`
    2. YAML list：
       ```
       allowed-tools:
         - Read
         - Bash
       ```
    """
    # 注意：使用 [ \t]* 而非 \s*，避免跨行误吸 YAML list 首行（\s 包含 \n）
    inline_match = re.search(r"^allowed-tools:[ \t]*(.*)$", frontmatter, re.MULTILINE)
    if not inline_match:
        return []

    value = inline_match.group(1).strip()
    if value:
        # Inline 格式：逗号分隔，但保留 Bash(X, Y) 括号内的逗号
        items, depth, current = [], 0, ""
        for ch in value:
            if ch == "(":
                depth += 1
                current += ch
            elif ch == ")":
                depth -= 1
                current += ch
            elif ch == "," and depth == 0:
                items.append(current.strip())
                current = ""
            else:
                current += ch
        if current.strip():
            items.append(current.strip())
        return [item for item in items if item]

    # YAML list 格式
    list_match = re.search(
        r"^allowed-tools:\s*\n((?:\s+-\s+.+\n?)+)",
        frontmatter,
        re.MULTILINE,
    )
    if list_match:
        items = re.findall(r"-\s+(.+?)\s*$", list_match.group(1), re.MULTILINE)
        return [item.strip() for item in items if item.strip()]

    return []


def _extract_bash_patterns(allowed_tools: list) -> tuple:
    """提取 Bash 子模式，返回 (patterns, has_unrestricted_bash)。

    - `Bash` 不带括号 → has_unrestricted_bash=True（放行所有命令）
    - `Bash(X)` → patterns.append(X)
    """
    patterns = []
    has_unrestricted = False
    for tool in allowed_tools:
        if tool == "Bash":
            has_unrestricted = True
            continue
        m = re.match(r"^Bash\((.+)\)$", tool)
        if m:
            patterns.append(m.group(1))
    return patterns, has_unrestricted


def _command_matches_patterns(command: str, patterns: list) -> bool:
    """检查命令字符串是否匹配任一 Bash 子模式。

    模式语义（与 Claude Code 一致，glob 风格）:
    - `*` 匹配任意字符
    - `python*` 匹配 `python`, `python -c ...`, `python3 script.py`
    - `python .claude/skills/cc-cfg/*` 匹配带该前缀的任意路径
    """
    for pattern in patterns:
        regex_str = re.escape(pattern).replace(r"\*", ".*")
        if re.match("^" + regex_str + "$", command):
            return True
    return False


def _strip_fenced_blocks(content: str) -> str:
    """删除 ```...``` 代码块，保留行号（用空行占位）。"""
    lines = content.split("\n")
    in_block = False
    result = []
    for line in lines:
        if line.strip().startswith("```"):
            in_block = not in_block
            result.append("")
            continue
        result.append("" if in_block else line)
    return "\n".join(result)


def check_allowed_tools_inline_commands(skills_dir: Path, verbose: bool) -> list:
    """校验项 8: allowed-tools ↔ 内联命令一致性

    防 Iter 5 类 silent fail: SKILL.md 或 workflows/*.md 中使用 `!`command``
    内联 shell 命令，但 frontmatter 的 allowed-tools 未声明相应 Bash 权限，
    或 Bash 子模式未覆盖该命令。

    历史案例（Iter 5）：
    - cc-cfg: 原 `Bash(python .claude/skills/cc-cfg/*)` 太窄，inline
      `!`python -c ...`` 无法匹配 → 修为 `Bash(python*)`
    - cc-tag: 原缺 `Bash(basename*)` + `Bash(git*)`，inline `!`basename`/`!`git`
      无权限 → 补充两个子模式

    注意：仅检查 `!`command`` inline 语法（Claude Code Skill 执行语法）。
    ```bash ... ``` fenced 代码块视为文档示例，不触发检查。
    """
    errors = []
    inline_pattern = re.compile(r"!`([^`\n]+)`")
    fm_pattern = re.compile(r"^---\n(.*?)\n---\n", re.DOTALL)

    scanned_skills = 0
    scanned_commands = 0

    for skill_dir in sorted(skills_dir.iterdir()):
        if not skill_dir.is_dir() or not skill_dir.name.startswith("cc-"):
            continue

        skill_md = skill_dir / "SKILL.md"
        if not skill_md.exists():
            continue

        try:
            content = skill_md.read_text(encoding="utf-8")
        except Exception:
            continue

        fm_match = fm_pattern.match(content)
        if not fm_match:
            continue

        allowed_tools = _parse_allowed_tools(fm_match.group(1))
        if not allowed_tools:
            continue

        bash_patterns, has_unrestricted = _extract_bash_patterns(allowed_tools)
        scanned_skills += 1

        # 扫描 SKILL.md + workflows/**/*.md + 顶层 prompts.md / templates.md
        files_to_scan = [skill_md]
        for sub_name in ("workflows", "prompts", "templates"):
            sub_dir = skill_dir / sub_name
            if sub_dir.is_dir():
                files_to_scan.extend(sorted(sub_dir.rglob("*.md")))
        for top_file in ("prompts.md", "templates.md"):
            p = skill_dir / top_file
            if p.is_file() and p not in files_to_scan:
                files_to_scan.append(p)

        for md_file in files_to_scan:
            try:
                file_content = md_file.read_text(encoding="utf-8")
            except Exception:
                continue

            cleaned = _strip_fenced_blocks(file_content)

            for match in inline_pattern.finditer(cleaned):
                command_str = match.group(1).strip()
                if not command_str:
                    continue
                scanned_commands += 1

                if has_unrestricted:
                    continue

                if not _command_matches_patterns(command_str, bash_patterns):
                    line_no = cleaned[: match.start()].count("\n") + 1
                    rel_path = md_file.relative_to(skills_dir)
                    pattern_repr = bash_patterns if bash_patterns else ["无 Bash 权限"]
                    errors.append(
                        f"{rel_path}:{line_no} 内联命令 !`{command_str}` "
                        f"未被 allowed-tools 的 Bash 子模式覆盖 "
                        f"(当前 Bash: {pattern_repr})"
                    )

    if verbose:
        print(f"\n--- allowed-tools 内联命令一致性详细信息 ---")
        print(f"  扫描 skill 数: {scanned_skills}")
        print(f"  扫描 inline 命令数: {scanned_commands}")

    return errors


def check_subfile_references(skills_dir: Path, verbose: bool) -> list:
    """
    规则 12 (Iter 30): SKILL.md 子文件引用完整性检查

    扫描每个 SKILL.md 中的 Markdown 相对链接 [text](file.md)，
    验证引用的子文件在 skill 目录内实际存在。
    排除 shared-rules/ 和 http 开头的外部引用。
    """
    errors = []
    link_pattern = re.compile(r'\[([^\]]*)\]\(([^)]+\.md(?:#[^\)]*)?)\)')
    scanned_skills = 0
    scanned_links = 0
    skip_prefixes = ('shared-rules/', 'http', 'mailto:', '/')

    for skill_dir in sorted(skills_dir.iterdir()):
        if not skill_dir.is_dir() or skill_dir.name.startswith('.') or skill_dir.name == 'shared-rules':
            continue
        skill_md = skill_dir / 'SKILL.md'
        if not skill_md.exists():
            continue
        scanned_skills += 1
        content = skill_md.read_text(encoding='utf-8')

        # 排除 frontmatter（--- 之间的内容）
        body = content
        if content.startswith('---'):
            end = content.find('---', 3)
            if end != -1:
                body = content[end + 3:]

        for match in link_pattern.finditer(body):
            link_text, link_target = match.group(1), match.group(2)
            # 去除锚点
            link_path = link_target.split('#')[0]
            # 跳过外部引用
            if any(link_path.startswith(p) for p in skip_prefixes):
                continue
            scanned_links += 1
            target_path = (skill_dir / link_path).resolve()
            if not target_path.exists():
                errors.append(
                    f"{skill_dir.name}: SKILL.md 引用 [{link_text}]({link_path}) 但文件不存在 (规则 12)"
                )

    if verbose:
        print(f"\n--- 子文件引用完整性详细信息 ---")
        print(f"  扫描 skill 数: {scanned_skills}")
        print(f"  扫描链接数: {scanned_links}")

    return errors


def check_report_protocol_compliance(skills_dir: Path, verbose: bool) -> list:
    """
    规则 11 (Iter 24): data-report-protocol 合规性检查

    11A: 声明 report_generation: true 的 skill 必须有 report_protocol 字段
         且值为 "data-report-protocol"
    11B: 声明 report_generation: true 的 skill 必须有 report_protocol_mode 字段
         且值在 [full, grounding-only, evidence-chain] 之一
    11C: 声明 report_generation: true 的 skill 的 SKILL.md 内文必须引用
         "data-report-protocol" 字符串（证明真的引用了协议而非空声明）

    防范：Iter 21/22 引入的 8 个 report_generation 字段未来漂移（AP6 副本漂移），
    或新增 report skill 时漏配协议引用。
    """
    errors = []
    skill_dirs = [d for d in skills_dir.iterdir()
                  if d.is_dir() and d.name.startswith("cc-")]

    valid_modes = {"full", "grounding-only", "evidence-chain"}
    scanned = 0
    declared = 0

    for skill_dir in sorted(skill_dirs):
        skill_md = skill_dir / "SKILL.md"
        if not skill_md.exists():
            continue
        scanned += 1

        content = skill_md.read_text(encoding="utf-8")

        # 提取 frontmatter (--- 包围)
        m = re.match(r"^---\n(.*?)\n---", content, re.DOTALL)
        if not m:
            continue
        frontmatter = m.group(1)

        # 检查是否声明 report_generation: true
        if not re.search(r"^report_generation:\s*true\s*$", frontmatter, re.MULTILINE):
            continue
        declared += 1

        # 11A: report_protocol 字段必须存在且值正确
        rp_match = re.search(r"^report_protocol:\s*(\S+)\s*$", frontmatter, re.MULTILINE)
        if not rp_match:
            errors.append(
                f"{skill_dir.name}: 声明 report_generation: true 但缺失 report_protocol 字段 (规则 11A)"
            )
        elif rp_match.group(1) != "data-report-protocol":
            errors.append(
                f"{skill_dir.name}: report_protocol 应为 'data-report-protocol'，实际 '{rp_match.group(1)}' (规则 11A)"
            )

        # 11B: report_protocol_mode 字段必须存在 + 值合法
        rpm_match = re.search(r"^report_protocol_mode:\s*(\S+)\s*$", frontmatter, re.MULTILINE)
        if not rpm_match:
            errors.append(
                f"{skill_dir.name}: 声明 report_generation: true 但缺失 report_protocol_mode 字段 (规则 11B)"
            )
        elif rpm_match.group(1) not in valid_modes:
            errors.append(
                f"{skill_dir.name}: report_protocol_mode 值 '{rpm_match.group(1)}' 不合法，必须为 {sorted(valid_modes)} 之一 (规则 11B)"
            )

        # 11C: SKILL.md 内文必须引用 data-report-protocol
        body = content[m.end():]
        if "data-report-protocol" not in body:
            errors.append(
                f"{skill_dir.name}: SKILL.md 内文未引用 'data-report-protocol' 字符串，无法证明协议引用 (规则 11C)"
            )

    if verbose:
        print(f"\n--- data-report-protocol 合规性详细信息 ---")
        print(f"  扫描 skill 数: {scanned}")
        print(f"  声明 report_generation 数: {declared}")
        print(f"  有效 mode: {sorted(valid_modes)}")

    return errors


def main():
    parser = argparse.ArgumentParser(description="Skill 一致性校验脚本")
    parser.add_argument("--verbose", "-v", action="store_true", help="输出详细信息")
    args = parser.parse_args()

    # 基于脚本位置推算 skills 目录
    script_dir = Path(__file__).resolve().parent
    skills_dir = script_dir.parent.parent  # scripts -> cc-skill-creator -> skills

    if args.verbose:
        print(f"Skills 目录: {skills_dir}")
        print(f"skill-rules.json: {skills_dir / 'skill-rules.json'}")

    rules = load_skill_rules(skills_dir)
    actual_dirs = get_skill_dirs(skills_dir)

    all_errors = []
    all_warnings = []
    checks = [
        ("Skill 列表一致性", check_skill_list_consistency, (rules, actual_dirs, args.verbose)),
        ("禁止组合一致性", check_forbidden_combinations, (rules, args.verbose)),
        ("隐式依赖一致性", check_implicit_dependencies, (rules, args.verbose)),
        ("Tier 一致性", check_tier_consistency, (rules, args.verbose)),
        ("数据契约一致性", check_data_contracts, (rules, args.verbose)),
        # Iter 9 新增（防漂移元工具守护）
        ("shared-rules 路径引用一致性", check_shared_rules_paths, (skills_dir, args.verbose)),
        ("skill-orchestration 章节引用一致性", check_orchestration_chapter_refs, (skills_dir, args.verbose)),
        # Iter 10 新增（allowed-tools silent fail 机制化防范）
        ("allowed-tools 内联命令一致性", check_allowed_tools_inline_commands, (skills_dir, args.verbose)),
        # Iter 17 新增（AP6 同 skill 内部副本漂移防范）
        ("同 skill 内部步骤号引用一致性", check_intra_skill_step_refs, (skills_dir, args.verbose)),
        ("同 skill shared-rules 章节格式一致性", check_intra_skill_shared_rules_chapter_format, (skills_dir, args.verbose)),
        # Iter 24 新增（data-report-protocol 合规性 — 8 个 report_generation skill 长期防漂移）
        ("data-report-protocol 合规性", check_report_protocol_compliance, (skills_dir, args.verbose)),
        # Iter 30 新增（渐进披露子文件引用完整性 — SKILL.md 引用的子文件必须存在）
        ("子文件引用完整性", check_subfile_references, (skills_dir, args.verbose)),
    ]

    print("=" * 50)
    print("Skill 一致性校验")
    print("=" * 50)

    for check_name, check_fn, check_args in checks:
        result = check_fn(*check_args)

        # check_skill_list_consistency 返回 (errors, warnings) 元组
        if isinstance(result, tuple):
            errors, warnings = result
        else:
            errors = result
            warnings = []

        if errors:
            for err in errors:
                print(f"\n  [\u274c] {check_name}: {err}")
                all_errors.append(err)
        if warnings:
            for warn in warnings:
                print(f"\n  [\u26a0\ufe0f] {check_name}: {warn}")
                all_warnings.append(warn)
        if not errors and not warnings:
            print(f"\n  [\u2705] {check_name}检查通过")

    print("\n" + "=" * 50)
    if all_errors:
        print(f"结果: {len(all_errors)} 个错误, {len(all_warnings)} 个警告")
        sys.exit(1)
    elif all_warnings:
        print(f"结果: 全部通过, {len(all_warnings)} 个警告")
        sys.exit(0)
    else:
        print("结果: 全部通过")
        sys.exit(0)


if __name__ == "__main__":
    main()
