"""cc-web-tester 脚本测试（T7）"""
import json
import tempfile
import zipfile
from pathlib import Path

import pytest
import sys

SCRIPTS_DIR = Path(__file__).parent.parent / "cc-web-tester" / "scripts"
sys.path.insert(0, str(SCRIPTS_DIR))

from xmind_common import gen_id, make_topic, build_module_title, write_xmind


class TestGenId:
    def test_deterministic(self):
        assert gen_id("test") == gen_id("test")

    def test_different_seeds(self):
        assert gen_id("a") != gen_id("b")

    def test_length(self):
        assert len(gen_id("test")) == 24


class TestMakeTopic:
    def test_basic(self):
        t = make_topic("Title", "id1")
        assert t["title"] == "Title"
        assert t["id"] == "id1"
        assert t["class"] == "topic"
        assert "children" not in t
        assert "labels" not in t
        assert "notes" not in t

    def test_with_children(self):
        child = make_topic("Child", "child1")
        t = make_topic("Parent", "parent1", children=[child])
        assert t["children"]["attached"] == [child]

    def test_with_labels(self):
        t = make_topic("Title", "id1", labels=["P0", "P1"])
        assert t["labels"] == ["P0", "P1"]

    def test_with_notes(self):
        t = make_topic("Title", "id1", notes="Some notes")
        assert t["notes"]["plain"]["content"] == "Some notes"


class TestBuildModuleTitle:
    def test_no_patterns(self):
        assert build_module_title("Login", []) == "Login"

    def test_with_patterns(self):
        assert build_module_title("Login", ["happy", "error"]) == "Login [happy],[error]"


class TestWriteXmind:
    def test_creates_valid_zip(self):
        content = [{"id": "root", "title": "Test"}]
        with tempfile.NamedTemporaryFile(suffix=".xmind", delete=False) as f:
            write_xmind(content, f.name)
            assert zipfile.is_zipfile(f.name)
            with zipfile.ZipFile(f.name, "r") as zf:
                names = zf.namelist()
                assert "content.json" in names
                assert "metadata.json" in names
                assert "manifest.json" in names
                data = json.loads(zf.read("content.json"))
                assert data == content
        Path(f.name).unlink()


class TestJsonToMd:
    """测试 json-to-md.py 的 generate_md 函数"""

    def test_generate_md(self):
        # 动态导入（文件名含连字符）
        import importlib.util
        spec = importlib.util.spec_from_file_location("json_to_md", SCRIPTS_DIR / "json-to-md.py")
        mod = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(mod)

        data = {
            "title": "Test Suite",
            "url": "http://example.com",
            "date": "2026-03-12",
            "modules": [{
                "name": "Login Module",
                "cases": [{
                    "id": "TC-001",
                    "title": "Login Success",
                    "priority": "P0",
                    "precondition": "User exists",
                    "steps": ["Open login page", "Enter credentials", "Click login"],
                    "expected": "Dashboard shown",
                }]
            }]
        }
        md = mod.generate_md(data)
        assert "# Test Suite" in md
        assert "TC-001" in md
        assert "Login Success" in md
        assert "P0" in md
        assert "Open login page" in md
        assert "Dashboard shown" in md
        assert "总用例数" in md
