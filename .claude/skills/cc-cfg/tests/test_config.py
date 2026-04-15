"""配置加载测试"""
import os
import tempfile

import pytest

from core.config import (
    ConnectionConfig,
    DefaultsConfig,
    CfgSkillConfig,
    load_config,
)


class TestConnectionConfig:
    def test_defaults(self):
        c = ConnectionConfig()
        assert c.base_url == "http://moka.dmz.prod.caijj.net"
        assert c.timeout == 10

    def test_custom_values(self):
        c = ConnectionConfig(base_url="http://test.com", timeout=30)
        assert c.base_url == "http://test.com"
        assert c.timeout == 30

    def test_token_file_default(self, monkeypatch):
        """未指定 token_file 时使用环境变量或默认路径"""
        monkeypatch.delenv("MOKA_TOKEN_FILE", raising=False)
        c = ConnectionConfig()
        assert "moka-prod-x-token.json" in c.token_file

    def test_token_file_from_env(self, monkeypatch):
        """环境变量 MOKA_TOKEN_FILE 优先"""
        monkeypatch.setenv("MOKA_TOKEN_FILE", "/tmp/custom-token.json")
        c = ConnectionConfig()
        assert c.token_file == "/tmp/custom-token.json"


class TestDefaultsConfig:
    def test_defaults(self):
        d = DefaultsConfig()
        assert d.app_name == "vipship"

    def test_custom_app_name(self):
        d = DefaultsConfig(app_name="other-app")
        assert d.app_name == "other-app"


class TestLoadConfig:
    def test_load_valid_config(self):
        yaml_content = """
connection:
  base_url: "http://test.example.com"
  token_file: "/tmp/test-token.json"
  timeout: 20

defaults:
  app_name: "test-app"
"""
        with tempfile.NamedTemporaryFile(mode="w", suffix=".yaml", delete=False) as f:
            f.write(yaml_content)
            f.flush()

            config = load_config(f.name)
            assert config.connection.base_url == "http://test.example.com"
            assert config.connection.token_file == "/tmp/test-token.json"
            assert config.connection.timeout == 20
            assert config.defaults.app_name == "test-app"

        os.unlink(f.name)

    def test_missing_config_uses_defaults(self):
        """配置文件不存在时使用默认值"""
        config = load_config("/nonexistent/path/config.yaml")
        assert config.connection.base_url == "http://moka.dmz.prod.caijj.net"
        assert config.connection.timeout == 10
        assert config.defaults.app_name == "vipship"

    def test_env_var_override(self, tmp_path):
        yaml_content = """
connection:
  base_url: "http://env.example.com"
  token_file: "/tmp/test.json"
"""
        config_file = tmp_path / "config.yaml"
        config_file.write_text(yaml_content)

        old_val = os.environ.get("CFG_SKILL_CONFIG")
        os.environ["CFG_SKILL_CONFIG"] = str(config_file)
        try:
            config = load_config()
            assert config.connection.base_url == "http://env.example.com"
        finally:
            if old_val is None:
                os.environ.pop("CFG_SKILL_CONFIG", None)
            else:
                os.environ["CFG_SKILL_CONFIG"] = old_val

    def test_partial_config(self, tmp_path):
        """只配置部分字段，其余使用默认值"""
        yaml_content = """
defaults:
  app_name: "custom-app"
"""
        config_file = tmp_path / "config.yaml"
        config_file.write_text(yaml_content)

        config = load_config(str(config_file))
        assert config.defaults.app_name == "custom-app"
        assert config.connection.base_url == "http://moka.dmz.prod.caijj.net"
        assert config.connection.timeout == 10

    def test_empty_yaml(self, tmp_path):
        """空 YAML 文件使用全部默认值"""
        config_file = tmp_path / "config.yaml"
        config_file.write_text("")

        config = load_config(str(config_file))
        assert config.connection.base_url == "http://moka.dmz.prod.caijj.net"
        assert config.defaults.app_name == "vipship"

    def test_invalid_yaml(self, tmp_path):
        """格式错误的 YAML 应抛出异常"""
        config_file = tmp_path / "config.yaml"
        config_file.write_text("{{invalid: yaml: content")

        with pytest.raises(Exception):
            load_config(str(config_file))
