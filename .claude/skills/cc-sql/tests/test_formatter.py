"""格式化测试"""
import json

from core.formatter import format_json, format_table, output_error, output_success


class TestFormatJson:
    def test_basic(self):
        data = {"success": True, "count": 3}
        result = format_json(data)
        parsed = json.loads(result)
        assert parsed["success"] is True
        assert parsed["count"] == 3

    def test_chinese(self):
        data = {"message": "查询成功"}
        result = format_json(data)
        assert "查询成功" in result  # ensure_ascii=False

    def test_indent(self):
        data = {"a": 1}
        result = format_json(data, indent=4)
        assert "    " in result


class TestFormatTable:
    def test_basic(self):
        columns = ["id", "name"]
        rows = [[1, "alice"], [2, "bob"]]
        result = format_table(columns, rows)
        assert "id" in result
        assert "alice" in result
        assert "bob" in result

    def test_truncate_long_values(self):
        columns = ["data"]
        rows = [["x" * 100]]
        result = format_table(columns, rows, max_column_width=20)
        assert "..." in result

    def test_none_values(self):
        columns = ["id", "name"]
        rows = [[1, None]]
        result = format_table(columns, rows)
        assert "1" in result

    def test_empty_rows(self):
        columns = ["id"]
        rows = []
        result = format_table(columns, rows)
        assert "id" in result


class TestOutputSuccess:
    def test_json_output(self, capsys):
        data = {"success": True, "row_count": 2}
        output_success(data, fmt="json")
        captured = capsys.readouterr()
        parsed = json.loads(captured.out)
        assert parsed["success"] is True

    def test_table_output(self, capsys):
        data = {"success": True, "row_count": 1, "execution_time_ms": 100}
        output_success(
            data, fmt="table",
            columns=["id", "name"], rows=[[1, "test"]]
        )
        captured = capsys.readouterr()
        assert "id" in captured.out
        assert "test" in captured.out
        assert "行数: 1" in captured.out


class TestOutputError:
    def test_error_to_stderr(self, capsys):
        output_error("测试错误", "TEST_ERROR")
        captured = capsys.readouterr()
        assert captured.out == ""
        parsed = json.loads(captured.err)
        assert parsed["success"] is False
        assert parsed["error"] == "测试错误"
        assert parsed["error_code"] == "TEST_ERROR"
