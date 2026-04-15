"""配置中心 HTTP 客户端（仅 prod 环境，GET 方式通过 Moka 网关）"""
import json
import os
import uuid
import urllib.request
import urllib.error
import urllib.parse
from typing import Any, Dict, Optional

from .config import CfgSkillConfig
from .exceptions import CfgConnectionError, CfgNotFoundError


class CfgClient:
    """配置中心查询客户端"""

    # 配置页面查询路径模板
    CONFIG_PATH = "/midwareopr/mgr/simbusiness/env/prod/configs/page/{appName}"

    def __init__(self, config: CfgSkillConfig):
        conn = config.connection
        self.base_url = conn.base_url.rstrip("/")
        self.timeout = conn.timeout
        self.token_file = conn.token_file
        self._token: Optional[str] = None
        self._token_mtime: float = 0

    def _load_token(self) -> str:
        """加载 x-token（基于 mtime 热更新）"""
        try:
            mtime = os.path.getmtime(self.token_file)
            if self._token is None or mtime > self._token_mtime:
                with open(self.token_file, "r", encoding="utf-8") as f:
                    data = json.load(f)
                    self._token = data.get("xToken")
                    self._token_mtime = mtime
                    if not self._token:
                        raise CfgConnectionError("Token 文件中缺少 xToken 字段")
            return self._token
        except FileNotFoundError:
            raise CfgConnectionError(f"Token 文件不存在: {self.token_file}\n请先登录 moka.dmz.prod.caijj.net")
        except json.JSONDecodeError:
            raise CfgConnectionError(f"Token 文件格式错误: {self.token_file}")

    def query(self, key: str, app_name: str) -> Dict[str, Any]:
        """查询配置

        Returns:
            {
                "success": True,
                "config_name": "...",
                "app_name": "...",
                "value": <parsed JSON or raw string>
            }
        """
        token = self._load_token()
        path = self.CONFIG_PATH.format(appName=app_name)
        url = f"{self.base_url}{path}"

        params = {
            "r_i": str(uuid.uuid4()),
            "t_a": str(uuid.uuid4()),
            "source": "false",
            "searchName": key,
            "labels": "",
            "pageNo": "1",
            "pageSize": "10",
        }
        full_url = f"{url}?{urllib.parse.urlencode(params)}"

        headers = {
            "Content-Type": "application/json",
            "X-TOKEN": token,
        }

        req = urllib.request.Request(full_url, headers=headers, method="GET")

        try:
            with urllib.request.urlopen(req, timeout=self.timeout) as response:
                result = json.loads(response.read().decode("utf-8"))
        except urllib.error.HTTPError as e:
            raise CfgConnectionError(f"HTTP 错误: {e.code} - {e.reason}")
        except urllib.error.URLError as e:
            raise CfgConnectionError(f"网络错误: {e.reason}")

        items = result.get("items", [])
        if not items:
            raise CfgNotFoundError(f"未找到配置: {key}")

        simbusiness_bo = items[0].get("simbusinessBo", {})
        config_name = simbusiness_bo.get("configName", key)
        value_bos = simbusiness_bo.get("valueBos", [])

        if not value_bos:
            raise CfgNotFoundError(f"配置 {key} 没有值")

        values = value_bos[0].get("values", [])
        if not values:
            raise CfgNotFoundError(f"配置 {key} 没有值")

        raw_value = values[0].get("value", "")

        # 尝试解析为 JSON
        try:
            parsed_value = json.loads(raw_value)
        except (json.JSONDecodeError, TypeError):
            parsed_value = raw_value

        return {
            "success": True,
            "config_name": config_name,
            "app_name": app_name,
            "value": parsed_value,
        }
