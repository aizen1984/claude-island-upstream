"""MySQL 直连客户端"""
import re
import time
from typing import Any, Dict, List, Optional

import pymysql

from .config import SkillsConfig
from .exceptions import ConnectionError


def _validate_identifier(name: str) -> str:
    """验证并返回安全的 SQL 标识符（表名、列名等）"""
    if not name:
        raise ValueError("标识符不能为空")
    if not re.match(r'^[a-zA-Z_][a-zA-Z0-9_]*$', name):
        raise ValueError(f"非法标识符: {name}")
    return name


class MysqlClient:
    """MySQL 直连客户端，与 MokaClient 接口一致"""

    def __init__(self, config: SkillsConfig):
        conn = config.connection
        self._host = conn.host
        self._port = conn.port
        self._user = conn.user
        self._password = conn.password
        self._default_db = config.defaults.schema_name
        self._conn: Optional[pymysql.Connection] = None

    def _get_connection(self, database: str = None) -> pymysql.Connection:
        """获取或创建 MySQL 连接"""
        db = database or self._default_db
        if self._conn and self._conn.open:
            self._conn.select_db(db)
            return self._conn
        self._conn = pymysql.connect(
            host=self._host,
            port=self._port,
            user=self._user,
            password=self._password,
            database=db,
            charset="utf8mb4",
            connect_timeout=10,
            read_timeout=30,
        )
        return self._conn

    def close(self):
        """关闭连接"""
        if self._conn and self._conn.open:
            self._conn.close()
            self._conn = None

    def execute_sql(self, database: str, sql: str, instance_name: str = None) -> Dict[str, Any]:
        """执行 SQL 查询"""
        start_time = time.time()
        try:
            conn = self._get_connection(database)
            with conn.cursor() as cursor:
                cursor.execute(sql)
                columns = [desc[0] for desc in cursor.description] if cursor.description else []
                rows = [list(row) for row in cursor.fetchall()]
        except pymysql.Error as e:
            raise ConnectionError(f"MySQL 查询失败: {e}")

        execution_time = int((time.time() - start_time) * 1000)
        return {
            "success": True,
            "columns": columns,
            "rows": rows,
            "row_count": len(rows),
            "execution_time_ms": execution_time,
        }

    def get_schemas(self) -> List[Dict[str, str]]:
        """获取可用的 schema 列表"""
        result = self.execute_sql("information_schema", "SHOW DATABASES")
        return [
            {"instanceName": "mysql-direct", "schemaName": row[0]}
            for row in result["rows"]
        ]

    def get_tables(self, instance_name: str, schema_name: str) -> List[str]:
        """获取表列表"""
        result = self.execute_sql(schema_name, "SHOW TABLES")
        return [row[0] for row in result["rows"]]

    def get_columns(self, database: str, table: str, instance_name: str = None) -> List[Dict[str, Any]]:
        """获取表的字段信息"""
        safe_table = _validate_identifier(table)
        result = self.execute_sql(database, f"SHOW FULL COLUMNS FROM `{safe_table}`")
        return self._extract_columns(result)

    def _extract_columns(self, result: Dict) -> List[Dict[str, Any]]:
        """从结果中提取字段信息"""
        columns = []
        headers = result.get("columns", [])
        col_index = {col.upper(): i for i, col in enumerate(headers)}

        for row in result.get("rows", []):
            columns.append({
                "name": row[col_index.get("FIELD", 0)],
                "type": row[col_index.get("TYPE", 1)] if len(row) > 1 else "",
                "nullable": row[col_index.get("NULL", 3)] == "YES" if len(row) > 3 else True,
                "key": row[col_index.get("KEY", 4)] if len(row) > 4 else None,
                "default": row[col_index.get("DEFAULT", 5)] if len(row) > 5 else None,
                "comment": row[col_index.get("COMMENT", 8)] if len(row) > 8 else None,
            })
        return columns

    def get_indexes(self, database: str, table: str, instance_name: str = None) -> List[Dict[str, Any]]:
        """获取表的索引信息"""
        safe_table = _validate_identifier(table)
        result = self.execute_sql(database, f"SHOW INDEX FROM `{safe_table}`")
        return self._extract_indexes(result)

    def _extract_indexes(self, result: Dict) -> List[Dict[str, Any]]:
        """从结果中提取索引信息"""
        indexes_map = {}
        headers = result.get("columns", [])
        col_index = {col.upper(): i for i, col in enumerate(headers)} if headers else {}

        for row in result.get("rows", []):
            key_name = row[col_index.get("KEY_NAME", 2)]
            column_name = row[col_index.get("COLUMN_NAME", 4)]
            non_unique = row[col_index.get("NON_UNIQUE", 1)]
            index_type = row[col_index.get("INDEX_TYPE", 10)] if len(row) > 10 else "BTREE"

            if key_name not in indexes_map:
                indexes_map[key_name] = {
                    "name": key_name,
                    "type": index_type or "BTREE",
                    "unique": non_unique == 0,
                    "columns": [],
                }
            indexes_map[key_name]["columns"].append(column_name)

        return list(indexes_map.values())
