"""共享 fixtures"""
import json
from pathlib import Path

import pytest

SKILLS_DIR = Path(__file__).parent.parent
SKILL_RULES_PATH = SKILLS_DIR / "skill-rules.json"

SKILL_NAMES = [
    "cc-planner", "cc-work-mode", "cc-code-writer",
    "cc-code-reviewer", "cc-design", "cc-java-backend",
    "cc-diagram", "cc-api-analyzer", "cc-web-tester",
    "sql", "cfg", "cc-skill-creator",
]


@pytest.fixture
def skills_dir():
    return SKILLS_DIR


@pytest.fixture
def skill_rules():
    with open(SKILL_RULES_PATH, "r", encoding="utf-8") as f:
        return json.load(f)


@pytest.fixture
def skill_names():
    return SKILL_NAMES
