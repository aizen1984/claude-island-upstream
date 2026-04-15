"""组合规则 + 禁止组合测试（T13）"""
import json
import re
from pathlib import Path

import pytest

SKILLS_DIR = Path(__file__).parent.parent
SKILL_RULES_PATH = SKILLS_DIR / "skill-rules.json"


def _load_rules():
    with open(SKILL_RULES_PATH, "r", encoding="utf-8") as f:
        return json.load(f)


class TestCombinationRules:
    """组合规则消歧测试"""

    @pytest.fixture
    def rules(self):
        return _load_rules()

    def _get_combo_rules(self, rules):
        return rules.get("combinationRules", {}).get("rules", [])

    def test_review_analyze_combo_triggers(self, rules):
        """审查+接口 应触发消歧"""
        combo = None
        for rule in self._get_combo_rules(rules):
            if rule["id"] == "review-analyze-combo":
                combo = rule
                break
        assert combo is not None, "review-analyze-combo rule not found"

        # 应匹配的输入
        assert re.search(combo["pattern"], "审查一下这个接口的代码")
        assert combo["resolution"] == "clarify"

    def test_write_sql_combo_triggers(self, rules):
        """写SQL 应自动路由到 sql"""
        combo = None
        for rule in self._get_combo_rules(rules):
            if rule["id"] == "write-sql-combo":
                combo = rule
                break
        assert combo is not None, "write-sql-combo rule not found"

        assert re.search(combo["pattern"], "帮我写个SQL查询语句")
        assert combo["resolution"] == "auto"
        assert combo["autoSelect"] == "sql"

    def test_sql_diagram_combo_exists(self, rules):
        """sql-diagram-combo 规则存在"""
        ids = [r["id"] for r in self._get_combo_rules(rules)]
        assert "sql-diagram-combo" in ids


class TestForbiddenCombinations:
    """禁止组合测试"""

    @pytest.fixture
    def rules(self):
        return _load_rules()

    def test_design_codewriter_forbidden(self, rules):
        """design -> code-writer 直连被禁止"""
        found = False
        for combo in rules.get("forbiddenCombinations", []):
            if combo.get("from") == "cc-design" and combo.get("to") == "cc-code-writer":
                found = True
                break
        assert found, "design -> code-writer forbidden combination not found"

    def test_workmode_nesting_forbidden(self, rules):
        """work-mode 嵌套被禁止"""
        found = False
        for combo in rules.get("forbiddenCombinations", []):
            if combo.get("id") == "no-workmode-nesting":
                found = True
                break
        assert found, "work-mode nesting forbidden combination not found"

    def test_codewriter_nesting_forbidden(self, rules):
        """code-writer 嵌套被禁止"""
        found = False
        for combo in rules.get("forbiddenCombinations", []):
            if combo.get("id") == "no-codewriter-nesting":
                found = True
                break
        assert found, "code-writer nesting forbidden combination not found"

    def test_all_forbidden_skills_exist(self, rules):
        """禁止组合中的 from/to skill 名称必须存在（非 skill 的特殊值如 EXECUTE 除外）"""
        valid_skills = set(rules["skills"].keys())
        special_values = {"EXECUTE"}  # 非 skill 的特殊值
        for combo in rules.get("forbiddenCombinations", []):
            for field in ("from", "to"):
                val = combo.get(field, "")
                if val and val not in special_values:
                    assert val in valid_skills, f"Unknown skill '{val}' in forbidden combo {combo.get('id')}"
