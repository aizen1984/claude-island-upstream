"""CfgClient 测试"""
import json
import os
import tempfile
from unittest.mock import patch, MagicMock

import pytest

from core.client import CfgClient
from core.config import CfgSkillConfig, ConnectionConfig, DefaultsConfig
from core.exceptions import CfgConnectionError, CfgNotFoundError


@pytest.fixture
def token_file(tmp_path):
    """创建临时 token 文件"""
    token_path = tmp_path / "token.json"
    token_path.write_text(json.dumps({"xToken": "test-token-abc"}))
    return str(token_path)


@pytest.fixture
def config(token_file):
    """创建测试配置"""
    return CfgSkillConfig(
        connection=ConnectionConfig(
            base_url="http://test.example.com",
            token_file=token_file,
            timeout=5,
        ),
        defaults=DefaultsConfig(app_name="test-app"),
    )


@pytest.fixture
def client(config):
    return CfgClient(config)


class TestTokenLoading:
    def test_load_token_success(self, client, token_file):
        """正常加载 token"""
        token = client._load_token()
        assert token == "test-token-abc"

    def test_load_token_cached(self, client):
        """第二次调用使用缓存"""
        token1 = client._load_token()
        token2 = client._load_token()
        assert token1 == token2

    def test_load_token_hot_reload(self, client, token_file):
        """token 文件更新后热加载"""
        token1 = client._load_token()
        assert token1 == "test-token-abc"

        # 更新 token 文件（需要确保 mtime 变化）
        import time
        time.sleep(0.05)
        with open(token_file, "w") as f:
            json.dump({"xToken": "new-token-xyz"}, f)

        token2 = client._load_token()
        assert token2 == "new-token-xyz"

    def test_load_token_file_not_found(self):
        """token 文件不存在"""
        config = CfgSkillConfig(
            connection=ConnectionConfig(
                token_file="/nonexistent/token.json",
            ),
            defaults=DefaultsConfig(),
        )
        client = CfgClient(config)

        with pytest.raises(CfgConnectionError, match="Token 文件不存在"):
            client._load_token()

    def test_load_token_invalid_json(self, tmp_path):
        """token 文件不是合法 JSON"""
        bad_file = tmp_path / "bad-token.json"
        bad_file.write_text("not json content")

        config = CfgSkillConfig(
            connection=ConnectionConfig(token_file=str(bad_file)),
            defaults=DefaultsConfig(),
        )
        client = CfgClient(config)

        with pytest.raises(CfgConnectionError, match="Token 文件格式错误"):
            client._load_token()

    def test_load_token_missing_field(self, tmp_path):
        """token 文件中缺少 xToken 字段"""
        no_token_file = tmp_path / "no-token.json"
        no_token_file.write_text(json.dumps({"other": "value"}))

        config = CfgSkillConfig(
            connection=ConnectionConfig(token_file=str(no_token_file)),
            defaults=DefaultsConfig(),
        )
        client = CfgClient(config)

        with pytest.raises(CfgConnectionError, match="缺少 xToken 字段"):
            client._load_token()


class TestQuery:
    def _mock_response(self, data: dict):
        """构造 mock HTTP 响应"""
        mock_resp = MagicMock()
        mock_resp.read.return_value = json.dumps(data).encode("utf-8")
        mock_resp.__enter__ = lambda s: s
        mock_resp.__exit__ = MagicMock(return_value=False)
        return mock_resp

    def test_query_success_json_value(self, client):
        """查询成功，值为 JSON"""
        response_data = {
            "items": [
                {
                    "simbusinessBo": {
                        "configName": "my.config",
                        "valueBos": [
                            {
                                "values": [
                                    {"value": '{"key": "val", "num": 42}'}
                                ]
                            }
                        ],
                    }
                }
            ]
        }

        with patch("urllib.request.urlopen", return_value=self._mock_response(response_data)):
            result = client.query("my.config", "test-app")

        assert result["success"] is True
        assert result["config_name"] == "my.config"
        assert result["app_name"] == "test-app"
        assert result["value"] == {"key": "val", "num": 42}

    def test_query_success_string_value(self, client):
        """查询成功，值为普通字符串（非 JSON）"""
        response_data = {
            "items": [
                {
                    "simbusinessBo": {
                        "configName": "my.string.config",
                        "valueBos": [
                            {
                                "values": [
                                    {"value": "plain text value"}
                                ]
                            }
                        ],
                    }
                }
            ]
        }

        with patch("urllib.request.urlopen", return_value=self._mock_response(response_data)):
            result = client.query("my.string.config", "test-app")

        assert result["success"] is True
        assert result["value"] == "plain text value"

    def test_query_not_found(self, client):
        """配置不存在"""
        response_data = {"items": []}

        with patch("urllib.request.urlopen", return_value=self._mock_response(response_data)):
            with pytest.raises(CfgNotFoundError, match="未找到配置"):
                client.query("nonexistent.key", "test-app")

    def test_query_empty_value_bos(self, client):
        """配置存在但 valueBos 为空"""
        response_data = {
            "items": [
                {
                    "simbusinessBo": {
                        "configName": "empty.config",
                        "valueBos": [],
                    }
                }
            ]
        }

        with patch("urllib.request.urlopen", return_value=self._mock_response(response_data)):
            with pytest.raises(CfgNotFoundError, match="没有值"):
                client.query("empty.config", "test-app")

    def test_query_empty_values(self, client):
        """valueBos 存在但 values 为空"""
        response_data = {
            "items": [
                {
                    "simbusinessBo": {
                        "configName": "empty.config",
                        "valueBos": [{"values": []}],
                    }
                }
            ]
        }

        with patch("urllib.request.urlopen", return_value=self._mock_response(response_data)):
            with pytest.raises(CfgNotFoundError, match="没有值"):
                client.query("empty.config", "test-app")

    def test_query_http_error(self, client):
        """HTTP 错误"""
        import urllib.error

        mock_error = urllib.error.HTTPError(
            url="http://test.com", code=401, msg="Unauthorized",
            hdrs=None, fp=None
        )

        with patch("urllib.request.urlopen", side_effect=mock_error):
            with pytest.raises(CfgConnectionError, match="HTTP 错误: 401"):
                client.query("some.key", "test-app")

    def test_query_network_error(self, client):
        """网络错误"""
        import urllib.error

        mock_error = urllib.error.URLError("Connection refused")

        with patch("urllib.request.urlopen", side_effect=mock_error):
            with pytest.raises(CfgConnectionError, match="网络错误"):
                client.query("some.key", "test-app")

    def test_query_url_construction(self, client):
        """验证请求 URL 构造正确"""
        response_data = {
            "items": [
                {
                    "simbusinessBo": {
                        "configName": "test",
                        "valueBos": [{"values": [{"value": "v"}]}],
                    }
                }
            ]
        }

        with patch("urllib.request.urlopen", return_value=self._mock_response(response_data)) as mock_open:
            client.query("test.key", "my-app")

            # 验证 URL 包含正确的 appName 和 searchName
            call_args = mock_open.call_args
            req = call_args[0][0]
            assert "/my-app" in req.full_url
            assert "searchName=test.key" in req.full_url
            assert req.get_header("X-token") == "test-token-abc"
