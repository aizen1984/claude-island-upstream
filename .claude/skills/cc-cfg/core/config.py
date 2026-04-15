"""配置加载模块"""
import os
from dataclasses import dataclass
from pathlib import Path

import yaml

_DEFAULT_CONFIG_PATH = Path(__file__).parent.parent / "config.yaml"


@dataclass
class ConnectionConfig:
    base_url: str = "http://moka.dmz.prod.caijj.net"
    token_file: str = ""
    timeout: int = 10

    def __post_init__(self):
        if not self.token_file:
            self.token_file = os.getenv(
                "MOKA_TOKEN_FILE",
                str(Path.home() / "x-token" / "moka-prod-x-token.json"),
            )


@dataclass
class DefaultsConfig:
    app_name: str = "vipship"


@dataclass
class CfgSkillConfig:
    connection: ConnectionConfig
    defaults: DefaultsConfig


def load_config(config_path: str = None) -> CfgSkillConfig:
    """加载配置"""
    path = config_path or os.getenv("CFG_SKILL_CONFIG") or str(_DEFAULT_CONFIG_PATH)
    path = Path(path)

    if not path.exists():
        # 使用默认值
        return CfgSkillConfig(
            connection=ConnectionConfig(),
            defaults=DefaultsConfig(),
        )

    with open(path, "r", encoding="utf-8") as f:
        data = yaml.safe_load(f) or {}

    return CfgSkillConfig(
        connection=ConnectionConfig(**data.get("connection", {})),
        defaults=DefaultsConfig(**data.get("defaults", {})),
    )
