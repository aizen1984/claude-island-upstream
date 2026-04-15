"""关键词激活 + skipConditions 测试（T12）"""
import json
import re
from pathlib import Path

import pytest

SKILLS_DIR = Path(__file__).parent.parent
SKILL_RULES_PATH = SKILLS_DIR / "skill-rules.json"


def _load_rules():
    with open(SKILL_RULES_PATH, "r", encoding="utf-8") as f:
        return json.load(f)


def _match_skill(user_input: str, rules: dict) -> list:
    """模拟 skill 匹配逻辑：返回匹配的 skill 名称列表"""
    matched = []
    for name, skill in rules["skills"].items():
        triggers = skill.get("promptTriggers", {})
        skip = skill.get("skipConditions", {})

        # 检查 skipConditions
        skip_kws = skip.get("keywords", [])
        if any(kw in user_input for kw in skip_kws):
            continue

        # 检查 keywords
        keywords = triggers.get("keywords", [])
        if any(kw in user_input for kw in keywords):
            matched.append(name)
            continue

        # 检查 intentPatterns
        patterns = triggers.get("intentPatterns", [])
        for pattern in patterns:
            if re.search(pattern, user_input):
                matched.append(name)
                break

    return matched


class TestKeywordActivation:
    """每个 Skill 至少有一个 keyword 能触发它"""

    @pytest.fixture
    def rules(self):
        return _load_rules()

    @pytest.mark.parametrize("skill_name,test_input", [
        ("cc-code-reviewer", "帮我审查一下这个代码"),
        ("cc-design", "帮我写个设计文档"),
        ("cc-planner", "帮我做个开发计划"),
        ("cc-work-mode", "干活帮我批量实现"),
        ("cc-code-writer", "帮我写代码实现这个功能"),
        ("cc-api-analyzer", "分析一下这个接口的调用链"),
        ("cc-diagram", "帮我画个流程图"),
        ("cc-web-tester", "帮我测试这个网页"),
        ("sql", "帮我查一下数据库"),
        ("cfg", "查一下配置中心"),
        ("cc-skill-creator", "帮我创建一个新skill"),
    ])
    def test_keyword_triggers(self, rules, skill_name, test_input):
        matched = _match_skill(test_input, rules)
        assert skill_name in matched, f"'{test_input}' should trigger {skill_name}, got {matched}"


class TestSkipConditions:
    """skipConditions 应阻止触发"""

    @pytest.fixture
    def rules(self):
        return _load_rules()

    @pytest.mark.parametrize("skill_name,test_input", [
        ("cc-code-reviewer", "帮我修复bug这个异常报错"),
        ("cc-design", "干活帮我实现功能"),
        ("cc-planner", "干活帮我写代码"),
        ("cc-work-mode", "帮我画图"),
        ("cc-code-writer", "干活模式帮我实现"),
    ])
    def test_skip_prevents_activation(self, rules, skill_name, test_input):
        matched = _match_skill(test_input, rules)
        assert skill_name not in matched, f"'{test_input}' should NOT trigger {skill_name}"


class TestIntentPatterns:
    """intentPatterns 正则匹配测试"""

    @pytest.fixture
    def rules(self):
        return _load_rules()

    @pytest.mark.parametrize("skill_name,test_input", [
        ("cc-code-reviewer", "看看这段代码有没有问题"),
        ("cc-code-reviewer", "这个实现是否合理"),
        ("cc-design", "生成一个技术设计文档"),
        ("cc-planner", "帮我规划一下这个功能的任务"),
        ("cc-code-writer", "帮我实现一个登录接口"),
        ("cc-api-analyzer", "分析一下用户认证接口"),
    ])
    def test_intent_pattern_matches(self, rules, skill_name, test_input):
        matched = _match_skill(test_input, rules)
        assert skill_name in matched, f"'{test_input}' should trigger {skill_name} via intent pattern"
