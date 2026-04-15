"""同步 Moka HTTP 客户端（从 app/clients/moka_client.py 提取）"""
import json
import os
import re
import time
import uuid
from typing import Any, Dict, List, Optional

import httpx

from .config import SkillsConfig
from .exceptions import ConnectionError


def create_client(config: SkillsConfig):
    """根据连接类型创建对应的客户端"""
    if config.connection.type == "mysql":
        from .mysql_client import MysqlClient
        return MysqlClient(config)
    return MokaClient(config)


def _validate_identifier(name: str) -> str:
    """验证并返回安全的 SQL 标识符（表名、列名等）"""
    if not name:
        raise ValueError("标识符不能为空")
    if not re.match(r'^[a-zA-Z_][a-zA-Z0-9_]*$', name):
        raise ValueError(f"非法标识符: {name}")
    return name


class MokaClient:
    """同步 Moka API 客户端"""

    def __init__(self, config: SkillsConfig):
        conn = config.connection
        self.firekylin_url = conn.firekylin_url.rstrip("/")
        self.timeout = conn.timeout
        self.token_file = conn.token_file
        self._token: Optional[str] = None
        self._token_mtime: float = 0
        self._http_client: Optional[httpx.Client] = None
        self._defaults = config.defaults

    def _get_client(self) -> httpx.Client:
        """获取或创建 HTTP 客户端"""
        if self._http_client is None or self._http_client.is_closed:
            self._http_client = httpx.Client(
                timeout=self.timeout,
                proxy=None,
                limits=httpx.Limits(max_connections=100, max_keepalive_connections=20),
            )
        return self._http_client

    def close(self):
        """关闭 HTTP 客户端"""
        if self._http_client:
            self._http_client.close()
            self._http_client = None

    def _load_token(self) -> str:
        """加载 x-token，支持热更新"""
        try:
            mtime = os.path.getmtime(self.token_file)
            if self._token is None or mtime > self._token_mtime:
                with open(self.token_file, "r", encoding="utf-8") as f:
                    data = json.load(f)
                    self._token = data.get("xToken")
                    self._token_mtime = mtime
                    if not self._token:
                        raise ConnectionError("Token 文件中缺少 xToken 字段")
            return self._token
        except FileNotFoundError:
            raise ConnectionError(f"Token 文件不存在: {self.token_file}")
        except json.JSONDecodeError:
            raise ConnectionError(f"Token 文件格式错误: {self.token_file}")

    def _get_headers(self) -> Dict[str, str]:
        """获取请求头"""
        return {
            "Content-Type": "application/json",
            "x-token": self._load_token(),
        }

    def _handle_request_error(self, e: Exception, url: str) -> None:
        """统一处理 HTTP 请求错误"""
        if isinstance(e, httpx.TimeoutException):
            raise ConnectionError(f"请求超时: {url}")
        elif isinstance(e, httpx.HTTPStatusError):
            raise ConnectionError(f"HTTP 错误 {e.response.status_code}: {e.response.text}")
        elif isinstance(e, httpx.RequestError):
            raise ConnectionError(f"请求失败: {type(e).__name__}: {str(e)}")
        else:
            raise ConnectionError(f"未知错误: {str(e)}")

    def _extract_data_from_response(self, result: Any, operation: str) -> List:
        """从 API 响应中提取数据"""
        if isinstance(result, list):
            return result
        if result.get("code") != 0:
            raise ConnectionError(f"{operation}失败: {result.get('message', '未知错误')}")
        return result.get("data", [])

    def _request_firekylin(self, path: str, params: Optional[Dict] = None) -> Dict[str, Any]:
        """发送 Firekylin API 请求"""
        url = f"{self.firekylin_url}{path}"
        headers = self._get_headers()

        if params is None:
            params = {}
        params["r_i"] = str(uuid.uuid4())
        params["t_a"] = self._load_token()

        client = self._get_client()
        try:
            response = client.get(url=url, headers=headers, params=params)
            response.raise_for_status()
            return response.json()
        except Exception as e:
            self._handle_request_error(e, url)

    def _build_exec_query_request(self, database: str, sql: str, instance_name: str = None) -> Dict[str, Any]:
        """构建 SQL 执行查询请求参数"""
        url = f"{self.firekylin_url}/midwareopr/firekylin/exec-query"
        headers = self._get_headers()

        params = {
            "r_i": str(uuid.uuid4()),
            "t_a": self._load_token(),
        }

        json_data = {
            "instanceName": instance_name or self._defaults.instance_name,
            "schemaName": database,
            "queryStatement": sql,
        }

        return {
            "url": url,
            "headers": headers,
            "params": params,
            "json_data": json_data,
        }

    def _parse_firekylin_response(self, result: Dict[str, Any], execution_time_ms: int) -> Dict[str, Any]:
        """解析 Firekylin SQL 执行响应"""
        query_status = result.get("queryStatus")
        if query_status != "SUCCESS":
            error_msg = (
                result.get("queryErrorMsg")
                or result.get("queryResultMsg")
                or result.get("message")
                or "查询执行失败"
            )
            raise ConnectionError(error_msg)

        # 提取列名（去掉表名前缀）
        raw_columns = result.get("resultMeta", [])
        columns = [col.split('.')[-1] if '.' in col else col for col in raw_columns]

        # 提取数据行（对象数组 → 二维数组）
        result_data = result.get("result", [])
        rows = []
        for row_obj in result_data:
            if isinstance(row_obj, dict):
                row = [row_obj.get(col) for col in raw_columns]
                rows.append(row)

        return {
            "success": True,
            "columns": columns,
            "rows": rows,
            "row_count": len(rows),
            "execution_time_ms": execution_time_ms,
        }

    # ---- 业务方法 ----

    def get_schemas(self) -> List[Dict[str, str]]:
        """获取可用的 schema 列表"""
        result = self._request_firekylin(
            path="/midwareopr/firekylin/mgr/auth/mysql-schemas",
        )
        data = self._extract_data_from_response(result, "获取 schema 列表")
        return [
            {
                "instanceName": item.get("instanceName", ""),
                "schemaName": item.get("schemaName", ""),
            }
            for item in data
        ]

    def get_tables(self, instance_name: str, schema_name: str) -> List[str]:
        """通过 Firekylin API 获取表列表"""
        result = self._request_firekylin(
            path="/midwareopr/firekylin/mgr/database/listTablesForQuery",
            params={
                "instanceName": instance_name,
                "schemaName": schema_name,
            },
        )
        data = self._extract_data_from_response(result, "获取表列表")
        return [item.get("tableName", "") for item in data if item.get("tableName")]

    def get_columns(self, database: str, table: str, instance_name: str = None) -> List[Dict[str, Any]]:
        """获取表的字段信息"""
        safe_table = _validate_identifier(table)
        result = self.execute_sql(
            database=database,
            sql=f"SHOW FULL COLUMNS FROM `{safe_table}`",
            instance_name=instance_name,
        )
        return self._extract_columns_from_exec_result(result)

    def _extract_columns_from_exec_result(self, result: Dict) -> List[Dict[str, Any]]:
        """从 execute_sql 结果中提取字段信息"""
        columns = []
        headers = result.get("columns", [])
        rows = result.get("rows", [])
        col_index = {col.upper(): i for i, col in enumerate(headers)} if headers else {}

        for row in rows:
            if isinstance(row, list):
                column_info = {
                    "name": row[col_index.get("FIELD", 0)] if col_index else row[0],
                    "type": row[col_index.get("TYPE", 1)] if col_index else (row[1] if len(row) > 1 else ""),
                    "nullable": (row[col_index.get("NULL", 2)] if col_index else (row[2] if len(row) > 2 else "YES")) == "YES",
                    "key": row[col_index.get("KEY", 3)] if col_index else (row[3] if len(row) > 3 else None),
                    "default": row[col_index.get("DEFAULT", 4)] if col_index else (row[4] if len(row) > 4 else None),
                    "comment": row[col_index.get("COMMENT", 8)] if col_index else (row[8] if len(row) > 8 else None),
                }
                columns.append(column_info)

        return columns

    def get_indexes(self, database: str, table: str, instance_name: str = None) -> List[Dict[str, Any]]:
        """获取表的索引信息"""
        safe_table = _validate_identifier(table)
        result = self.execute_sql(
            database=database,
            sql=f"SHOW INDEX FROM `{safe_table}`",
            instance_name=instance_name,
        )
        return self._extract_indexes_from_exec_result(result)

    def _extract_indexes_from_exec_result(self, result: Dict) -> List[Dict[str, Any]]:
        """从 execute_sql 结果中提取索引信息"""
        indexes_map = {}
        headers = result.get("columns", [])
        rows = result.get("rows", [])
        col_index = {col.upper(): i for i, col in enumerate(headers)} if headers else {}

        for row in rows:
            if isinstance(row, list):
                key_name = row[col_index.get("KEY_NAME", 2)] if col_index else (row[2] if len(row) > 2 else "")
                column_name = row[col_index.get("COLUMN_NAME", 4)] if col_index else (row[4] if len(row) > 4 else "")
                non_unique = row[col_index.get("NON_UNIQUE", 1)] if col_index else (row[1] if len(row) > 1 else 1)
                index_type = row[col_index.get("INDEX_TYPE", 10)] if col_index else (row[10] if len(row) > 10 else "BTREE")

                if key_name not in indexes_map:
                    indexes_map[key_name] = {
                        "name": key_name,
                        "type": index_type or "BTREE",
                        "unique": non_unique == 0 or non_unique == "0",
                        "columns": [],
                    }
                indexes_map[key_name]["columns"].append(column_name)

        return list(indexes_map.values())

    def execute_sql(self, database: str, sql: str, instance_name: str = None) -> Dict[str, Any]:
        """执行 SQL 查询"""
        start_time = time.time()
        request = self._build_exec_query_request(database, sql, instance_name)

        client = self._get_client()
        try:
            response = client.post(
                url=request["url"],
                headers=request["headers"],
                params=request["params"],
                json=request["json_data"],
            )
            response.raise_for_status()
            result = response.json()
        except Exception as e:
            self._handle_request_error(e, request["url"])

        execution_time = int((time.time() - start_time) * 1000)
        return self._parse_firekylin_response(result, execution_time)
