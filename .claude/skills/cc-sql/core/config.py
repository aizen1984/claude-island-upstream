"""配置加载模块（dataclass 实现，无 pydantic 依赖）"""
import os
from dataclasses import dataclass, field
from pathlib import Path

import yaml

from .exceptions import ConfigError

# 默认配置文件路径
_DEFAULT_CONFIG_PATH = Path(__file__).parent.parent / "config.yaml"


@dataclass
class ConnectionConfig:
    type: str = "firekylin"
    firekylin_url: str = "http://moka.dmz.prod.caijj.net"
    token_file: str = ""
    timeout: int = 30
    # MySQL 直连字段
    host: str = ""
    port: int = 3306
    user: str = ""
    password: str = ""

    def __post_init__(self):
        if self.type == "firekylin" and not self.token_file:
            self.token_file = os.getenv(
                "MOKA_TOKEN_FILE",
                str(Path.home() / "x-token" / "moka-prod-x-token.json"),
            )


@dataclass
class DefaultsConfig:
    instance_name: str = ""
    schema_name: str = "vipship"


@dataclass
class SafetyConfig:
    max_rows: int = 1000
    allow_select_star: bool = False
    allowed_statements: list = field(
        default_factory=lambda: ["SELECT", "SHOW", "DESCRIBE", "DESC", "EXPLAIN"]
    )


@dataclass
class OutputConfig:
    format: str = "json"
    max_column_width: int = 50
    json_indent: int = 2


@dataclass
class CacheConfig:
    enabled: bool = True
    dir: str = ""
    ttl: int = 86400  # 24 hours

    def __post_init__(self):
        if not self.dir:
            self.dir = str(Path.home() / ".cache" / "claude-sql")
        else:
            self.dir = str(Path(self.dir).expanduser())


@dataclass
class SkillsConfig:
    connection: ConnectionConfig = field(default_factory=ConnectionConfig)
    defaults: DefaultsConfig = field(default_factory=DefaultsConfig)
    safety: SafetyConfig = field(default_factory=SafetyConfig)
    output: OutputConfig = field(default_factory=OutputConfig)
    cache: CacheConfig = field(default_factory=CacheConfig)
    env_name: str = "prod"


def load_config(config_path: str = None, env: str = None) -> SkillsConfig:
    """加载配置

    优先级：--config 参数 > 环境变量 SKILLS_CONFIG > 默认 skills/config.yaml
    env：环境名（prod/sit），None 时取 config 中的 default_env
    """
    path = config_path or os.getenv("SKILLS_CONFIG") or str(_DEFAULT_CONFIG_PATH)
    path = Path(path)

    if not path.exists():
        raise ConfigError(f"配置文件不存在: {path}")

    try:
        with open(path, "r", encoding="utf-8") as f:
            data = yaml.safe_load(f) or {}
    except yaml.YAMLError as e:
        raise ConfigError(f"配置文件格式错误: {e}")

    # 多环境解析
    env_name = env or data.get("default_env", "prod")
    environments = data.get("environments")
    if environments:
        env_config = environments.get(env_name)
        if not env_config:
            available = ", ".join(environments.keys())
            raise ConfigError(f"未知环境: {env_name}（可用: {available}）")

        conn_type = env_config.get("type", "firekylin")

        connection = ConnectionConfig(
            type=conn_type,
            firekylin_url=env_config.get("firekylin_url", ""),
            token_file=env_config.get("token_file", ""),
            timeout=env_config.get("timeout", 30),
            host=env_config.get("host", ""),
            port=env_config.get("port", 3306),
            user=env_config.get("user", ""),
            password=env_config.get("password", ""),
        )
        defaults = DefaultsConfig(
            instance_name=env_config.get("instance_name", ""),
            schema_name=env_config.get("schema_name", "vipship"),
        )
    else:
        connection = ConnectionConfig(**data.get("connection", {}))
        defaults = DefaultsConfig(**data.get("defaults", {}))

    return SkillsConfig(
        connection=connection,
        defaults=defaults,
        safety=SafetyConfig(**data.get("safety", {})),
        output=OutputConfig(**data.get("output", {})),
        cache=CacheConfig(**data.get("cache", {})),
        env_name=env_name,
    )
