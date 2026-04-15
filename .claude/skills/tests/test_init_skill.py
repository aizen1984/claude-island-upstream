"""cc-skill-creator/init_skill.py 单元测试（T5）"""
import tempfile
from pathlib import Path

import pytest
import sys

sys.path.insert(0, str(Path(__file__).parent.parent / "cc-skill-creator" / "scripts"))

from init_skill import normalize_skill_name, title_case_skill_name, parse_resources, init_skill


class TestNormalizeSkillName:
    def test_basic(self):
        assert normalize_skill_name("my-skill") == "my-skill"

    def test_uppercase(self):
        assert normalize_skill_name("My-Skill") == "my-skill"

    def test_spaces(self):
        assert normalize_skill_name("my new skill") == "my-new-skill"

    def test_special_chars(self):
        assert normalize_skill_name("my_skill!@#") == "my-skill"

    def test_consecutive_hyphens(self):
        assert normalize_skill_name("my---skill") == "my-skill"

    def test_leading_trailing_hyphens(self):
        assert normalize_skill_name("-my-skill-") == "my-skill"

    def test_empty_after_normalize(self):
        assert normalize_skill_name("!!!") == ""

    def test_numbers(self):
        assert normalize_skill_name("skill-v2") == "skill-v2"


class TestTitleCaseSkillName:
    def test_basic(self):
        assert title_case_skill_name("my-new-skill") == "My New Skill"

    def test_single_word(self):
        assert title_case_skill_name("sql") == "Sql"


class TestParseResources:
    def test_empty(self):
        assert parse_resources("") == []
        assert parse_resources(None) == []

    def test_valid(self):
        result = parse_resources("scripts,references")
        assert result == ["scripts", "references"]

    def test_dedup(self):
        result = parse_resources("scripts,scripts,references")
        assert result == ["scripts", "references"]

    def test_invalid_exits(self):
        with pytest.raises(SystemExit):
            parse_resources("scripts,invalid_resource")


class TestInitSkill:
    def test_create_basic(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            result = init_skill("test-skill", tmpdir, [], False)
            assert result is not None
            assert (result / "SKILL.md").exists()
            content = (result / "SKILL.md").read_text()
            assert "name: test-skill" in content
            assert "Test Skill" in content

    def test_create_with_resources(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            result = init_skill("test-skill", tmpdir, ["scripts", "references"], False)
            assert (result / "scripts").is_dir()
            assert (result / "references").is_dir()

    def test_create_with_examples(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            result = init_skill("test-skill", tmpdir, ["scripts"], True)
            assert (result / "scripts" / "example.py").exists()

    def test_duplicate_fails(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            init_skill("test-skill", tmpdir, [], False)
            result = init_skill("test-skill", tmpdir, [], False)
            assert result is None
