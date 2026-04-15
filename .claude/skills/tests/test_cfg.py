"""cfg 单元测试（T4）"""
import json
import os
import tempfile
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest
import yaml

# 添加 cfg 到路径
import sys
sys.path.insert(0, str(Path(__file__).parent.parent / "cfg"))

from core.config import ConnectionConfig, DefaultsConfig, CfgSkillConfig, load_config
from core.client import CfgClient
from core.exceptions import CfgConnectionError, CfgNotFoundError


# ===== Config Tests =====

class TestConnectionConfig:
    def test_defaults(self):
        c = ConnectionConfig()
        assert c.base_url == "http://moka.dmz.prod.caijj.net"
        assert c.timeout == 10

    def test_token_file_from_env(self):
        with patch.dict(os.environ, {"MOKA_TOKEN_FILE": "/tmp/test-token.json"}):
            c = ConnectionConfig()
            assert c.token_file == "/tmp/test-token.json"

    def test_custom_values(self):
        c = ConnectionConfig(base_url="http://test", timeout=5, token_file="/tmp/t.json")
        assert c.base_url == "http://test"
        assert c.timeout == 5


class TestDefaultsConfig:
    def test_defaults(self):
        d = DefaultsConfig()
        assert d.app_name == "vipship"

    def test_custom(self):
        d = DefaultsConfig(app_name="myapp")
        assert d.app_name == "myapp"


class TestLoadConfig:
    def test_missing_file_returns_defaults(self):
        cfg = load_config("/nonexistent/path/config.yaml")
        assert cfg.connection.base_url == "http://moka.dmz.prod.caijj.net"
        assert cfg.defaults.app_name == "vipship"

    def test_load_valid_config(self):
        data = {
            "connection": {"base_url": "http://test", "timeout": 5},
            "defaults": {"app_name": "testapp"},
        }
        with tempfile.NamedTemporaryFile(mode="w", suffix=".yaml", delete=False) as f:
            yaml.dump(data, f)
            f.flush()
            cfg = load_config(f.name)
        os.unlink(f.name)
        assert cfg.connection.base_url == "http://test"
        assert cfg.defaults.app_name == "testapp"

    def test_env_var_override(self):
        data = {"defaults": {"app_name": "envapp"}}
        with tempfile.NamedTemporaryFile(mode="w", suffix=".yaml", delete=False) as f:
            yaml.dump(data, f)
            f.flush()
            with patch.dict(os.environ, {"CFG_SKILL_CONFIG": f.name}):
                cfg = load_config()
        os.unlink(f.name)
        assert cfg.defaults.app_name == "envapp"


# ===== Client Tests =====

class TestCfgClient:
    def _make_client(self, token_file="/tmp/fake-token.json"):
        config = CfgSkillConfig(
            connection=ConnectionConfig(token_file=token_file),
            defaults=DefaultsConfig(),
        )
        return CfgClient(config)

    def test_token_file_not_found(self):
        client = self._make_client("/nonexistent/token.json")
        with pytest.raises(CfgConnectionError, match="Token 文件不存在"):
            client._load_token()

    def test_token_file_no_xtoken(self):
        with tempfile.NamedTemporaryFile(mode="w", suffix=".json", delete=False) as f:
            json.dump({"other": "value"}, f)
            f.flush()
            client = self._make_client(f.name)
            with pytest.raises(CfgConnectionError, match="缺少 xToken"):
                client._load_token()
        os.unlink(f.name)

    def test_token_file_invalid_json(self):
        with tempfile.NamedTemporaryFile(mode="w", suffix=".json", delete=False) as f:
            f.write("not json")
            f.flush()
            client = self._make_client(f.name)
            with pytest.raises(CfgConnectionError, match="格式错误"):
                client._load_token()
        os.unlink(f.name)

    def test_load_token_success(self):
        with tempfile.NamedTemporaryFile(mode="w", suffix=".json", delete=False) as f:
            json.dump({"xToken": "test-token-123"}, f)
            f.flush()
            client = self._make_client(f.name)
            token = client._load_token()
            assert token == "test-token-123"
        os.unlink(f.name)

    def test_token_cached(self):
        """Token 应该只读取一次"""
        with tempfile.NamedTemporaryFile(mode="w", suffix=".json", delete=False) as f:
            json.dump({"xToken": "cached-token"}, f)
            f.flush()
            client = self._make_client(f.name)
            t1 = client._load_token()
            t2 = client._load_token()
            assert t1 == t2 == "cached-token"
        os.unlink(f.name)

    def test_query_not_found(self):
        """Mock HTTP 请求，模拟配置未找到"""
        client = self._make_client()

        mock_response = MagicMock()
        mock_response.read.return_value = json.dumps({"items": []}).encode()
        mock_response.__enter__ = lambda s: s
        mock_response.__exit__ = MagicMock(return_value=False)

        with patch.object(client, "_load_token", return_value="fake-token"), \
             patch("urllib.request.urlopen", return_value=mock_response):
            with pytest.raises(CfgNotFoundError, match="未找到配置"):
                client.query("nonexistent.key", "vipship")

    def test_query_success(self):
        """Mock HTTP 请求，模拟成功查询"""
        client = self._make_client()

        api_result = {
            "items": [{
                "simbusinessBo": {
                    "configName": "test.config",
                    "valueBos": [{
                        "values": [{"value": '{"key": "value"}'}]
                    }]
                }
            }]
        }
        mock_response = MagicMock()
        mock_response.read.return_value = json.dumps(api_result).encode()
        mock_response.__enter__ = lambda s: s
        mock_response.__exit__ = MagicMock(return_value=False)

        with patch.object(client, "_load_token", return_value="fake-token"), \
             patch("urllib.request.urlopen", return_value=mock_response):
            result = client.query("test.config", "vipship")
            assert result["success"] is True
            assert result["config_name"] == "test.config"
            assert result["value"] == {"key": "value"}

    def test_query_raw_string_value(self):
        """非 JSON 字符串值应直接返回"""
        client = self._make_client()

        api_result = {
            "items": [{
                "simbusinessBo": {
                    "configName": "simple.key",
                    "valueBos": [{"values": [{"value": "plain-text-value"}]}]
                }
            }]
        }
        mock_response = MagicMock()
        mock_response.read.return_value = json.dumps(api_result).encode()
        mock_response.__enter__ = lambda s: s
        mock_response.__exit__ = MagicMock(return_value=False)

        with patch.object(client, "_load_token", return_value="fake-token"), \
             patch("urllib.request.urlopen", return_value=mock_response):
            result = client.query("simple.key", "vipship")
            assert result["value"] == "plain-text-value"
