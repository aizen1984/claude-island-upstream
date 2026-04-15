#!/usr/bin/env python3
"""
Quick validation script for skills - minimal version
"""

import re
import sys
from pathlib import Path
from typing import Optional

try:
    import yaml
except ModuleNotFoundError:
    yaml = None

MAX_SKILL_NAME_LENGTH = 64


def _extract_frontmatter(content: str) -> Optional[str]:
    lines = content.splitlines()
    if not lines or lines[0].strip() != "---":
        return None
    for i in range(1, len(lines)):
        if lines[i].strip() == "---":
            return "\n".join(lines[1:i])
    return None


def _parse_simple_frontmatter(frontmatter_text: str) -> Optional[dict[str, str]]:
    """
    Minimal fallback parser used when PyYAML is unavailable.
    Supports simple `key: value` mappings used by SKILL.md frontmatter.
    """
    parsed: dict[str, str] = {}
    current_key: Optional[str] = None
    for raw_line in frontmatter_text.splitlines():
        stripped = raw_line.strip()
        if not stripped or stripped.startswith("#"):
            continue

        is_indented = raw_line[:1].isspace()
        if is_indented:
            if current_key is None:
                return None
            current_value = parsed[current_key]
            parsed[current_key] = (
                f"{current_value}\n{stripped}" if current_value else stripped
            )
            continue

        if ":" not in stripped:
            return None
        key, value = stripped.split(":", 1)
        key = key.strip()
        value = value.strip()
        if not key:
            return None
        if (value.startswith('"') and value.endswith('"')) or (
            value.startswith("'") and value.endswith("'")
        ):
            value = value[1:-1]
        parsed[key] = value
        current_key = key
    return parsed


def validate_skill(skill_path):
    """Basic validation of a skill"""
    skill_path = Path(skill_path)

    skill_md = skill_path / "SKILL.md"
    if not skill_md.exists():
        return False, "SKILL.md not found"

    try:
        content = skill_md.read_text(encoding="utf-8")
    except OSError as e:
        return False, f"Could not read SKILL.md: {e}"

    frontmatter_text = _extract_frontmatter(content)
    if frontmatter_text is None:
        return False, "Invalid frontmatter format"
    if yaml is not None:
        try:
            frontmatter = yaml.safe_load(frontmatter_text)
            if not isinstance(frontmatter, dict):
                return False, "Frontmatter must be a YAML dictionary"
        except yaml.YAMLError as e:
            return False, f"Invalid YAML in frontmatter: {e}"
    else:
        frontmatter = _parse_simple_frontmatter(frontmatter_text)
        if frontmatter is None:
            return (
                False,
                "Invalid YAML in frontmatter: unsupported syntax without PyYAML installed",
            )

    allowed_properties = {
        "name", "description", "license", "allowed-tools", "metadata",
        # Claude Code official extension fields
        # - disable-model-invocation: hide skill from Claude's auto-invocation (manual /skill only)
        #   docs: https://code.claude.com/docs/en/skills
        # - paths: limit skill activation to matching file patterns
        # - user-invocable: UI-level setting (does NOT prevent auto-invocation; use disable-model-invocation for that)
        #   ref: https://github.com/anthropics/claude-code/issues/19141
        "disable-model-invocation", "paths", "user-invocable",
        # Project-level extension fields
        "argument-hint", "context", "agent",
        # Iter 28 added: 2026-04-11 official spec new fields
        # - effort: low/medium/high/max (max only on Opus 4.6) — for long-running tasks
        # - hooks: skill lifecycle hooks
        # - model: override model when this skill is active
        # - shell: bash (default) or powershell
        "effort", "hooks", "model", "shell",
        # Data Report Protocol fields (Iter 20, shared-rules/data-report-protocol.md)
        # - report_generation: bool, 标记 skill 是否生成结构化数据报告
        # - report_protocol: 引用协议名称（默认 data-report-protocol）
        # - report_protocol_mode: full | grounding-only（opt-out 简单场景）
        "report_generation", "report_protocol", "report_protocol_mode",
        # Iteration Protocol fields (Iter 26, shared-rules/report-iteration-protocol.md)
        "iteration_protocol", "report_iteration_loop",
        "report_iteration_max_per_round", "report_iteration_gate_thresholds",
        "report_readability_scan",
    }
    # Deprecated fields: still accepted but emit a warning
    deprecated_fields = {"type", "priority"}

    present_deprecated = set(frontmatter.keys()) & deprecated_fields
    if present_deprecated:
        dep_str = ", ".join(sorted(present_deprecated))
        print(f"  ⚠️ {dep_str} 字段已废弃，请删除", file=sys.stderr)

    unexpected_keys = set(frontmatter.keys()) - allowed_properties - deprecated_fields
    if unexpected_keys:
        allowed = ", ".join(sorted(allowed_properties))
        unexpected = ", ".join(sorted(unexpected_keys))
        return (
            False,
            f"Unexpected key(s) in SKILL.md frontmatter: {unexpected}. Allowed properties are: {allowed}",
        )

    if "name" not in frontmatter:
        return False, "Missing 'name' in frontmatter"
    if "description" not in frontmatter:
        return False, "Missing 'description' in frontmatter"

    name = frontmatter.get("name", "")
    if not isinstance(name, str):
        return False, f"Name must be a string, got {type(name).__name__}"
    name = name.strip()
    if name:
        if not re.match(r"^[a-z0-9-]+$", name):
            return (
                False,
                f"Name '{name}' should be hyphen-case (lowercase letters, digits, and hyphens only)",
            )
        if name.startswith("-") or name.endswith("-") or "--" in name:
            return (
                False,
                f"Name '{name}' cannot start/end with hyphen or contain consecutive hyphens",
            )
        if len(name) > MAX_SKILL_NAME_LENGTH:
            return (
                False,
                f"Name is too long ({len(name)} characters). "
                f"Maximum is {MAX_SKILL_NAME_LENGTH} characters.",
            )

    description = frontmatter.get("description", "")
    if not isinstance(description, str):
        return False, f"Description must be a string, got {type(description).__name__}"
    description = description.strip()
    if description:
        if "<" in description or ">" in description:
            return False, "Description cannot contain angle brackets (< or >)"
        if len(description) > 1024:
            return (
                False,
                f"Description is too long ({len(description)} characters). Maximum is 1024 characters.",
            )
        # CSO check: description should not summarize workflow (SP experiment finding)
        # Use multi-word patterns to avoid false positives on common words like "then"
        workflow_patterns = [
            r"first\s.+then\s",    # "first X then Y" = sequential steps
            r"followed by",         # explicit sequence
            r"→.*→",               # multiple arrows = pipeline
            r"->.*->",             # multiple arrows
            r"step\s*[0-9]",       # "step 1", "step 2"
            r"\d+步",              # "6步" etc.
            r"先[^。]+再[^。]+然后",  # "先...再...然后"
            r"第[一二三四五六七八九十\d]+步",  # "第一步" etc.
        ]
        desc_lower = description.lower()
        cso_violation = False
        for pattern in workflow_patterns:
            if re.search(pattern, desc_lower):
                cso_violation = True
                cso_pattern = pattern
                break
        if cso_violation:
            return False, (
                f"CSO violation: description summarizes workflow (matched '{cso_pattern}'). "
                f"Description should only describe triggering conditions, not process steps."
            )

    return True, "Skill is valid!"


if __name__ == "__main__":
    if len(sys.argv) != 2:
        print("Usage: python quick_validate.py <skill_directory>")
        sys.exit(1)

    valid, message = validate_skill(sys.argv[1])
    print(message)
    sys.exit(0 if valid else 1)
