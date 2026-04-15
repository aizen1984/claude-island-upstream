"""文件行数限制测试（T11）"""
from pathlib import Path

import pytest

SKILLS_DIR = Path(__file__).parent.parent
MAX_LINES = 500


def _get_all_md_files():
    files = []
    for md in sorted(SKILLS_DIR.rglob("*.md")):
        rel = md.relative_to(SKILLS_DIR)
        if str(rel).startswith("tests/"):
            continue
        files.append(md)
    return files


class TestFileLimits:
    def test_skill_md_within_limit(self):
        """所有 SKILL.md 不超过 500 行"""
        violations = []
        for skill_md in sorted(SKILLS_DIR.glob("*/SKILL.md")):
            lines = len(skill_md.read_text().splitlines())
            if lines > MAX_LINES:
                violations.append(f"{skill_md.relative_to(SKILLS_DIR)}: {lines} lines")
        assert not violations, "SKILL.md files over limit:\n" + "\n".join(violations)

    def test_sub_files_within_limit(self):
        """所有子文件不超过 500 行"""
        violations = []
        for md in _get_all_md_files():
            if md.name == "SKILL.md":
                continue
            lines = len(md.read_text().splitlines())
            if lines > MAX_LINES:
                violations.append(f"{md.relative_to(SKILLS_DIR)}: {lines} lines")
        assert not violations, "Sub-files over limit:\n" + "\n".join(violations)

    def test_warn_near_limit(self):
        """报告接近限制的文件（>450 行）"""
        warnings = []
        for md in _get_all_md_files():
            lines = len(md.read_text().splitlines())
            if 450 < lines <= MAX_LINES:
                warnings.append(f"{md.relative_to(SKILLS_DIR)}: {lines} lines")
        if warnings:
            # 不失败，只记录
            print(f"\nWARNING - Files near limit (450-500):\n" + "\n".join(warnings))
