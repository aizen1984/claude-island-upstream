"""配置加载测试"""
import os
import tempfile

import pytest

from core.config import (
    ConnectionConfig,
    DefaultsConfig,
    OutputConfig,
    SafetyConfig,
    SkillsConfig,
    load_config,
)
from core.exceptions import ConfigError


class TestConnectionConfig:
    def test_defaults(self):
        c = ConnectionConfig()
        assert c.firekylin_url == "http://moka.dmz.prod.caijj.net"
        assert c.timeout == 30

    def test_custom_values(self):
        c = ConnectionConfig(firekylin_url="http://test.com", timeout=60)
        assert c.firekylin_url == "http://test.com"
        assert c.timeout == 60


class TestDefaultsConfig:
    def test_defaults(self):
        d = DefaultsConfig()
        assert d.instance_name == "dscommerce"
        assert d.schema_name == "vipship"


class TestSafetyConfig:
    def test_defaults(self):
        s = SafetyConfig()
        assert s.max_rows == 1000
        assert s.allow_select_star is False
        assert "SELECT" in s.allowed_statements


class TestOutputConfig:
    def test_defaults(self):
        o = OutputConfig()
        assert o.format == "json"
        assert o.json_indent == 2


class TestLoadConfig:
    def test_load_valid_config(self):
        yaml_content = """
connection:
  firekylin_url: "http://test.example.com"
  token_file: "/tmp/test-token.json"
  timeout: 15

defaults:
  instance_name: "test_instance"
  schema_name: "test_schema"

safety:
  max_rows: 500
  allow_select_star: true

output:
  format: "table"
  json_indent: 4
"""
        with tempfile.NamedTemporaryFile(mode="w", suffix=".yaml", delete=False) as f:
            f.write(yaml_content)
            f.flush()

            config = load_config(f.name)
            assert config.connection.firekylin_url == "http://test.example.com"
            assert config.connection.timeout == 15
            assert config.defaults.instance_name == "test_instance"
            assert config.safety.max_rows == 500
            assert config.safety.allow_select_star is True
            assert config.output.format == "table"

        os.unlink(f.name)

    def test_missing_config_file(self):
        with pytest.raises(ConfigError, match="配置文件不存在"):
            load_config("/nonexistent/path/config.yaml")

    def test_env_var_override(self, tmp_path):
        yaml_content = """
connection:
  firekylin_url: "http://env.example.com"
  token_file: "/tmp/test.json"
"""
        config_file = tmp_path / "config.yaml"
        config_file.write_text(yaml_content)

        old_val = os.environ.get("SKILLS_CONFIG")
        os.environ["SKILLS_CONFIG"] = str(config_file)
        try:
            config = load_config()
            assert config.connection.firekylin_url == "http://env.example.com"
        finally:
            if old_val is None:
                os.environ.pop("SKILLS_CONFIG", None)
            else:
                os.environ["SKILLS_CONFIG"] = old_val

    def test_partial_config(self, tmp_path):
        """只配置部分字段，其余使用默认值"""
        yaml_content = """
defaults:
  instance_name: "custom_instance"
"""
        config_file = tmp_path / "config.yaml"
        config_file.write_text(yaml_content)

        config = load_config(str(config_file))
        assert config.defaults.instance_name == "custom_instance"
        assert config.defaults.schema_name == "vipship"  # 默认值
        assert config.safety.max_rows == 1000  # 默认值
