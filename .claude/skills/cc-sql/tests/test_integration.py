"""集成测试（需要真实 API token）

运行方式:
    python -m pytest .claude/skills/sql/tests/test_integration.py -v
"""
import os
import subprocess
import sys

import pytest

# 跳过条件：token 文件不存在
SKILLS_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
CONFIG_PATH = os.path.join(SKILLS_DIR, "config.yaml")

# 尝试读取 token 文件路径
_skip_reason = None
try:
    import yaml
    with open(CONFIG_PATH) as f:
        _cfg = yaml.safe_load(f)
    _token_file = _cfg.get("connection", {}).get("token_file", "")
    if not os.path.exists(_token_file):
        _skip_reason = f"Token 文件不存在: {_token_file}"
except Exception as e:
    _skip_reason = f"无法加载配置: {e}"

skip_no_token = pytest.mark.skipif(_skip_reason is not None, reason=_skip_reason or "")


def _run_skill(script: str, *args: str) -> subprocess.CompletedProcess:
    """运行 skill 脚本"""
    cmd = [sys.executable, os.path.join(SKILLS_DIR, script)] + list(args)
    return subprocess.run(cmd, capture_output=True, text=True, cwd=SKILLS_DIR)


@skip_no_token
class TestDatabases:
    def test_list_all(self):
        r = _run_skill("databases.py")
        assert r.returncode == 0
        import json
        data = json.loads(r.stdout)
        assert data["success"] is True
        assert data["count"] > 0

    def test_filter(self):
        r = _run_skill("databases.py", "--filter", "vip")
        assert r.returncode == 0
        import json
        data = json.loads(r.stdout)
        assert data["success"] is True

    def test_table_format(self):
        r = _run_skill("databases.py", "--format", "table")
        assert r.returncode == 0
        assert "instanceName" in r.stdout


@skip_no_token
class TestTables:
    def test_default_database(self):
        r = _run_skill("tables.py")
        assert r.returncode == 0
        import json
        data = json.loads(r.stdout)
        assert data["success"] is True
        assert data["count"] > 0

    def test_with_filter(self):
        r = _run_skill("tables.py", "--filter", "order")
        assert r.returncode == 0


@skip_no_token
class TestColumns:
    def test_get_columns(self):
        # 先获取一个表名
        import json
        r = _run_skill("tables.py")
        tables = json.loads(r.stdout)["tables"]
        if not tables:
            pytest.skip("没有可用的表")
        table = tables[0]

        r = _run_skill("columns.py", table)
        assert r.returncode == 0
        data = json.loads(r.stdout)
        assert data["success"] is True
        assert data["count"] > 0


@skip_no_token
class TestDescribe:
    def test_describe_table(self):
        import json
        r = _run_skill("tables.py")
        tables = json.loads(r.stdout)["tables"]
        if not tables:
            pytest.skip("没有可用的表")
        table = tables[0]

        r = _run_skill("describe.py", table)
        assert r.returncode == 0
        data = json.loads(r.stdout)
        assert data["success"] is True
        assert "columns" in data
        assert "indexes" in data


@skip_no_token
class TestQuery:
    def test_simple_query(self):
        # 使用 SHOW TABLES 作为安全的测试查询
        r = _run_skill("query.py", "SHOW TABLES")
        assert r.returncode == 0
        import json
        data = json.loads(r.stdout)
        assert data["success"] is True

    def test_select_star_rejected(self):
        r = _run_skill("query.py", "SELECT * FROM some_table LIMIT 1")
        assert r.returncode == 1
        import json
        data = json.loads(r.stderr)
        assert data["success"] is False
        assert "SELECT *" in data["error"]

    def test_dangerous_sql_rejected(self):
        r = _run_skill("query.py", "DROP TABLE users")
        assert r.returncode == 1

    def test_table_format(self):
        r = _run_skill("query.py", "--format", "table", "SHOW TABLES")
        assert r.returncode == 0
