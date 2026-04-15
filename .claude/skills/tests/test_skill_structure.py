"""Skill 体系结构测试（T8）：SKILL.md frontmatter 校验"""
import re
from pathlib import Path

import pytest

try:
    import yaml
    HAS_YAML = True
except ImportError:
    HAS_YAML = False

SKILLS_DIR = Path(__file__).parent.parent
SKILL_NAMES = sorted(p.parent.name for p in SKILLS_DIR.glob("cc-*/SKILL.md"))


def _parse_frontmatter(content: str) -> dict:
    lines = content.splitlines()
    if not lines or lines[0].strip() != "---":
        return {}
    for i in range(1, len(lines)):
        if lines[i].strip() == "---":
            fm_text = "\n".join(lines[1:i])
            if HAS_YAML:
                return yaml.safe_load(fm_text) or {}
            # fallback 简单解析
            result = {}
            for line in fm_text.splitlines():
                if ":" in line:
                    k, v = line.split(":", 1)
                    result[k.strip()] = v.strip()
            return result
    return {}


@pytest.mark.parametrize("skill_name", SKILL_NAMES)
class TestSkillMdFrontmatter:
    def test_skill_md_exists(self, skill_name):
        assert (SKILLS_DIR / skill_name / "SKILL.md").exists()

    def test_has_name(self, skill_name):
        content = (SKILLS_DIR / skill_name / "SKILL.md").read_text()
        fm = _parse_frontmatter(content)
        assert "name" in fm, f"{skill_name}: missing 'name' in frontmatter"
        assert fm["name"] == skill_name

    def test_has_description(self, skill_name):
        content = (SKILLS_DIR / skill_name / "SKILL.md").read_text()
        fm = _parse_frontmatter(content)
        assert "description" in fm, f"{skill_name}: missing 'description'"
        assert len(fm["description"]) > 0

    def test_name_format(self, skill_name):
        content = (SKILLS_DIR / skill_name / "SKILL.md").read_text()
        fm = _parse_frontmatter(content)
        name = fm.get("name", "")
        assert re.match(r"^[a-z0-9-]+$", name), f"Invalid name format: {name}"
        assert len(name) <= 64

    def test_description_no_angle_brackets(self, skill_name):
        content = (SKILLS_DIR / skill_name / "SKILL.md").read_text()
        fm = _parse_frontmatter(content)
        desc = fm.get("description", "")
        assert "<" not in desc and ">" not in desc, f"Angle brackets in description: {desc}"

    def test_description_length(self, skill_name):
        content = (SKILLS_DIR / skill_name / "SKILL.md").read_text()
        fm = _parse_frontmatter(content)
        desc = fm.get("description", "")
        assert len(desc) <= 1024, f"Description too long: {len(desc)}"

    def test_skill_md_line_count(self, skill_name):
        content = (SKILLS_DIR / skill_name / "SKILL.md").read_text()
        lines = content.splitlines()
        assert len(lines) <= 500, f"{skill_name}/SKILL.md has {len(lines)} lines (max 500)"
