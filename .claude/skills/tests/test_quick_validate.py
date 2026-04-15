"""cc-skill-creator/quick_validate.py 单元测试（T6）"""
import tempfile
from pathlib import Path

import pytest
import sys

sys.path.insert(0, str(Path(__file__).parent.parent / "cc-skill-creator" / "scripts"))

from quick_validate import validate_skill


class TestValidateSkillPass:
    def test_valid_skill(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            skill_dir = Path(tmpdir) / "my-skill"
            skill_dir.mkdir()
            (skill_dir / "SKILL.md").write_text(
                "---\nname: my-skill\ndescription: A test skill\n---\n\n# My Skill\n"
            )
            valid, msg = validate_skill(str(skill_dir))
            assert valid is True

    def test_valid_all_12_skills(self):
        """验证所有 12 个 SKILL.md 通过校验"""
        skills_dir = Path(__file__).parent.parent
        for skill in [
            "cc-planner", "cc-work-mode", "cc-code-writer",
            "cc-code-reviewer", "cc-design", "cc-java-backend",
            "cc-diagram", "cc-api-analyzer", "cc-web-tester",
            "sql", "cfg", "cc-skill-creator",
        ]:
            skill_path = skills_dir / skill
            if skill_path.exists():
                valid, msg = validate_skill(str(skill_path))
                assert valid is True, f"{skill} failed: {msg}"


class TestValidateSkillFail:
    def test_missing_skill_md(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            valid, msg = validate_skill(tmpdir)
            assert valid is False
            assert "SKILL.md" in msg

    def test_missing_frontmatter(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            skill_dir = Path(tmpdir) / "my-skill"
            skill_dir.mkdir()
            (skill_dir / "SKILL.md").write_text("# No Frontmatter\n")
            valid, msg = validate_skill(str(skill_dir))
            assert valid is False

    def test_missing_name(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            skill_dir = Path(tmpdir) / "my-skill"
            skill_dir.mkdir()
            (skill_dir / "SKILL.md").write_text(
                "---\ndescription: test\n---\n"
            )
            valid, msg = validate_skill(str(skill_dir))
            assert valid is False

    def test_missing_description(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            skill_dir = Path(tmpdir) / "my-skill"
            skill_dir.mkdir()
            (skill_dir / "SKILL.md").write_text(
                "---\nname: my-skill\n---\n"
            )
            valid, msg = validate_skill(str(skill_dir))
            assert valid is False

    def test_invalid_name_format(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            skill_dir = Path(tmpdir) / "my-skill"
            skill_dir.mkdir()
            (skill_dir / "SKILL.md").write_text(
                "---\nname: My_Skill\ndescription: test\n---\n"
            )
            valid, msg = validate_skill(str(skill_dir))
            assert valid is False
            assert "hyphen-case" in msg

    def test_name_too_long(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            skill_dir = Path(tmpdir) / "my-skill"
            skill_dir.mkdir()
            long_name = "a" * 65
            (skill_dir / "SKILL.md").write_text(
                f"---\nname: {long_name}\ndescription: test\n---\n"
            )
            valid, msg = validate_skill(str(skill_dir))
            assert valid is False
            assert "too long" in msg

    def test_angle_brackets_in_description(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            skill_dir = Path(tmpdir) / "my-skill"
            skill_dir.mkdir()
            (skill_dir / "SKILL.md").write_text(
                "---\nname: my-skill\ndescription: ANALYZE->PLAN\n---\n"
            )
            valid, msg = validate_skill(str(skill_dir))
            assert valid is False
            assert "angle brackets" in msg

    def test_description_too_long(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            skill_dir = Path(tmpdir) / "my-skill"
            skill_dir.mkdir()
            long_desc = "x" * 1025
            (skill_dir / "SKILL.md").write_text(
                f"---\nname: my-skill\ndescription: {long_desc}\n---\n"
            )
            valid, msg = validate_skill(str(skill_dir))
            assert valid is False
            assert "too long" in msg
