"""输出格式化模块"""
import json
import sys
from typing import Any, Dict, List, Optional

from tabulate import tabulate


def format_json(data: Dict[str, Any], indent: int = 2) -> str:
    """格式化为 JSON 字符串"""
    return json.dumps(data, ensure_ascii=False, indent=indent, default=str)


def format_table(
    columns: List[str],
    rows: List[List[Any]],
    max_column_width: int = 50,
) -> str:
    """格式化为 ASCII 表格"""
    # 截断过长的值
    truncated_rows = []
    for row in rows:
        truncated_row = []
        for val in row:
            s = str(val) if val is not None else ""
            if len(s) > max_column_width:
                s = s[: max_column_width - 3] + "..."
            truncated_row.append(s)
        truncated_rows.append(truncated_row)

    return tabulate(truncated_rows, headers=columns, tablefmt="grid")


def output_success(
    data: Dict[str, Any],
    fmt: str = "json",
    indent: int = 2,
    columns: Optional[List[str]] = None,
    rows: Optional[List[List[Any]]] = None,
    max_column_width: int = 50,
) -> None:
    """统一成功输出到 stdout"""
    if fmt == "table" and columns is not None and rows is not None:
        print(format_table(columns, rows, max_column_width))
        # 追加元信息
        meta_parts = []
        if "row_count" in data:
            meta_parts.append(f"行数: {data['row_count']}")
        if "execution_time_ms" in data:
            meta_parts.append(f"耗时: {data['execution_time_ms']}ms")
        if meta_parts:
            print(f"\n({', '.join(meta_parts)})")
    else:
        print(format_json(data, indent))


def output_error(message: str, code: str = "ERROR") -> None:
    """统一错误输出到 stderr"""
    error_data = {
        "success": False,
        "error": message,
        "error_code": code,
    }
    print(format_json(error_data), file=sys.stderr)
