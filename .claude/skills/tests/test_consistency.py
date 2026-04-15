"""一致性测试（T10）：skill-rules.json 与 SKILL.md description + 正则有效性"""
import json
import re
from pathlib import Path

import pytest

try:
    import yaml
    HAS_YAML = True
except ImportError:
    HAS_YAML = False

SKILLS_DIR = Path(__file__).parent.parent
SKILL_RULES_PATH = SKILLS_DIR / "skill-rules.json"


def _load_rules():
    with open(SKILL_RULES_PATH, "r", encoding="utf-8") as f:
        return json.load(f)


def _parse_frontmatter(content: str) -> dict:
    lines = content.splitlines()
    if not lines or lines[0].strip() != "---":
        return {}
    for i in range(1, len(lines)):
        if lines[i].strip() == "---":
            fm_text = "\n".join(lines[1:i])
            if HAS_YAML:
                return yaml.safe_load(fm_text) or {}
            result = {}
            for line in fm_text.splitlines():
                if ":" in line:
                    k, v = line.split(":", 1)
                    result[k.strip()] = v.strip()
            return result
    return {}


class TestDescriptionConsistency:
    """skill-rules.json 与 SKILL.md 的 description 必须一致"""

    def test_all_descriptions_match(self):
        rules = _load_rules()
        mismatches = []
        for skill_name, skill_data in rules["skills"].items():
            skill_md = SKILLS_DIR / skill_name / "SKILL.md"
            if not skill_md.exists():
                mismatches.append(f"{skill_name}: SKILL.md not found")
                continue
            fm = _parse_frontmatter(skill_md.read_text())
            fm_desc = fm.get("description", "")
            rules_desc = skill_data.get("description", "")
            if fm_desc != rules_desc:
                mismatches.append(
                    f"{skill_name}:\n"
                    f"  rules: {rules_desc}\n"
                    f"  SKILL: {fm_desc}"
                )
        assert not mismatches, "Description mismatches:\n" + "\n".join(mismatches)


class TestPriorityOrderConsistency:
    """priorityOrder 中的每个 skill 都在 skills 对象中"""

    def test_priority_order_complete(self):
        rules = _load_rules()
        for name in rules["priorityOrder"]:
            assert name in rules["skills"], f"{name} in priorityOrder but not in skills"

    def test_skills_in_priority_order(self):
        rules = _load_rules()
        for name in rules["skills"]:
            assert name in rules["priorityOrder"], f"{name} in skills but not in priorityOrder"


class TestRegexValidity:
    """所有正则表达式必须是合法的"""

    def test_intent_patterns_valid(self):
        rules = _load_rules()
        for skill_name, skill_data in rules["skills"].items():
            patterns = skill_data.get("promptTriggers", {}).get("intentPatterns", [])
            for pattern in patterns:
                try:
                    re.compile(pattern)
                except re.error as e:
                    pytest.fail(f"{skill_name} invalid regex: {pattern} -> {e}")

    def test_combination_rules_valid(self):
        rules = _load_rules()
        combo_rules = rules.get("combinationRules", {}).get("rules", [])
        for rule in combo_rules:
            pattern = rule.get("pattern", "")
            try:
                re.compile(pattern)
            except re.error as e:
                pytest.fail(f"combinationRule {rule['id']} invalid regex: {pattern} -> {e}")


class TestForbiddenCombinations:
    """禁止组合的格式正确"""

    def test_forbidden_combinations_have_required_fields(self):
        rules = _load_rules()
        for combo in rules.get("forbiddenCombinations", []):
            assert "id" in combo, f"Missing 'id' in forbidden combination"
            assert "from" in combo, f"Missing 'from' in {combo.get('id', '?')}"
            assert "to" in combo, f"Missing 'to' in {combo.get('id', '?')}"
            assert "reason" in combo, f"Missing 'reason' in {combo.get('id', '?')}"


class TestObservabilityLogs:
    """observability-logs.md 结构完整性"""

    OBS_LOG_PATH = SKILLS_DIR / "shared-rules" / "observability-logs.md"

    def _read_content(self):
        return self.OBS_LOG_PATH.read_text(encoding="utf-8")

    def test_vault_search_section_exists(self):
        """Vault 检索日志章节必须存在"""
        content = self._read_content()
        assert "Vault 检索日志" in content, "缺少 Vault 检索日志章节"

    def test_vault_search_marked_mandatory(self):
        """Vault 检索日志必须标记为强制"""
        content = self._read_content()
        assert "强制" in content.split("Vault 检索日志")[1][:50], \
            "Vault 检索日志章节未标记为强制"

    def test_icon_table_has_vault_entry(self):
        """图标速查表必须包含 📖 Vault 条目"""
        content = self._read_content()
        assert "📖" in content, "图标速查表缺少 📖 条目"
        # 确认在表格行中
        lines = content.splitlines()
        vault_icon_lines = [l for l in lines if "📖" in l and "|" in l]
        assert vault_icon_lines, "📖 图标未出现在速查表表格中"

    def test_all_log_icons_in_table(self):
        """所有使用的日志图标都在速查表中"""
        content = self._read_content()
        # 从速查表中提取所有图标
        in_table = False
        table_icons = set()
        for line in content.splitlines():
            if "日志图标速查表" in line:
                in_table = True
                continue
            if in_table and line.startswith("|") and "`" in line:
                # 提取 `icon` 格式的图标
                icons = re.findall(r'`([^`]+)`', line)
                table_icons.update(icons)
            elif in_table and line.startswith("#"):
                break

        expected_icons = {"📋", "🔧", "📂", "🤖", "❓", "🔗", "📖"}
        missing = expected_icons - table_icons
        assert not missing, f"图标速查表缺少: {missing}"

    def test_section_numbers_sequential(self):
        """章节编号必须连续"""
        content = self._read_content()
        numbers = re.findall(r'^## (\d+)\.', content, re.MULTILINE)
        numbers = [int(n) for n in numbers]
        for i, n in enumerate(numbers):
            assert n == i + 1, f"章节编号不连续: 期望 {i+1}，实际 {n}"

    def test_no_garbled_text(self):
        """不应包含乱码字符（如 ��）"""
        content = self._read_content()
        assert "��" not in content, "文件包含乱码字符 ��"
