"""idaas token HTTP 客户端"""
import json
import os
import urllib.parse
import urllib.request
import urllib.error
from typing import Dict, Any, List

from .config import TokenSkillConfig


class IdaasTokenClient:

    TOGGLE_PATH = "/idaas/session/users:toggle"
    USERINFO_PATH = "/idaas/userinfo"
    SEARCH_USERS_PATH = "/idaas/v2/users"

    def __init__(self, config: TokenSkillConfig):
        self.config = config
        self._own_token = None

    def _load_own_token(self) -> str:
        """从本地文件加载自己的 x-token"""
        token_file = self.config.env.token_file
        if not os.path.exists(token_file):
            raise RuntimeError(
                f"Token 文件不存在: {token_file}\n"
                f"请先用 Chrome 插件（X-Token Grabber）访问 {self.config.env.base_url} 抓取 token"
            )
        with open(token_file, "r", encoding="utf-8") as f:
            data = json.load(f)
        token = data.get("xToken")
        if not token:
            raise RuntimeError(f"Token 文件缺少 xToken 字段: {token_file}")
        return token

    def _request(self, method: str, path: str, headers: dict, body: dict = None) -> dict:
        url = f"{self.config.env.base_url}{path}"
        data = json.dumps(body).encode("utf-8") if body else None
        req = urllib.request.Request(url, data=data, headers=headers, method=method)
        try:
            with urllib.request.urlopen(req, timeout=self.config.timeout) as resp:
                return json.loads(resp.read().decode("utf-8"))
        except urllib.error.HTTPError as e:
            body_text = ""
            try:
                body_text = e.read().decode("utf-8")
            except Exception:
                pass
            raise RuntimeError(f"HTTP {e.code}: {e.reason}\n{body_text}")
        except urllib.error.URLError as e:
            raise RuntimeError(f"网络错误: {e.reason}")

    def toggle(self, user_id: str) -> Dict[str, Any]:
        """切换到目标用户，返回其 x-token"""
        own_token = self._load_own_token()
        headers = {
            "Content-Type": "application/json",
            "x-token": own_token,
        }
        result = self._request("POST", self.TOGGLE_PATH, headers, body={
            "userId": user_id,
            "tenantId": self.config.env.tenant_id,
        })
        target_token = result.get("token")
        if not target_token:
            raise RuntimeError(f"toggle 返回中无 token 字段: {json.dumps(result, ensure_ascii=False)}")
        return {
            "success": True,
            "env": self.config.env_name,
            "target_user_id": user_id,
            "x_token": target_token,
            "raw_response": result,
        }

    def search_users(self, name: str, page_size: int = 10) -> Dict[str, Any]:
        """按姓名搜索用户，返回用户列表"""
        own_token = self._load_own_token()
        params = urllib.parse.urlencode({"pageNo": 1, "pageSize": page_size, "name": name})
        path = f"{self.SEARCH_USERS_PATH}?{params}"
        headers = {"x-token": own_token}
        result = self._request("GET", path, headers)
        users = result.get("data", [])
        return {
            "success": True,
            "env": self.config.env_name,
            "total": result.get("total", 0),
            "users": [
                {
                    "name": u.get("name"),
                    "userName": u.get("userName"),
                    "userId": u.get("userId"),
                    "email": u.get("email"),
                    "status": u.get("statusName"),
                    "org": u.get("corporationOrOrgList", [{}])[0].get("fillPathName", "") if u.get("corporationOrOrgList") else "",
                }
                for u in users
            ],
        }

    def verify(self, token: str) -> Dict[str, Any]:
        """验证 token 对应的用户信息"""
        headers = {"x-token": token}
        result = self._request("GET", self.USERINFO_PATH, headers)
        return {
            "success": True,
            "userinfo": result,
        }
