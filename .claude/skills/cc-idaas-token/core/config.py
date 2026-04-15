"""cc-idaas-token 配置加载"""
import os
from dataclasses import dataclass
from pathlib import Path

import yaml

_DEFAULT_CONFIG_PATH = Path(__file__).parent.parent / "config.yaml"


@dataclass
class EnvConfig:
    base_url: str
    token_file: str
    tenant_id: str


@dataclass
class TokenSkillConfig:
    env: EnvConfig
    env_name: str
    timeout: int


def load_config(config_path: str = None, env: str = None) -> TokenSkillConfig:
    path = Path(config_path or os.getenv("IDAAS_TOKEN_CONFIG") or str(_DEFAULT_CONFIG_PATH))

    if not path.exists():
        raise RuntimeError(f"配置文件不存在: {path}")

    with open(path, "r", encoding="utf-8") as f:
        data = yaml.safe_load(f) or {}

    env_name = env or data.get("default_env", "sit")
    environments = data.get("environments", {})
    env_data = environments.get(env_name)

    if not env_data:
        available = ", ".join(environments.keys())
        raise RuntimeError(f"未知环境: {env_name}（可用: {available}）")

    return TokenSkillConfig(
        env=EnvConfig(
            base_url=env_data["base_url"].rstrip("/"),
            token_file=env_data["token_file"],
            tenant_id=env_data["tenant_id"],
        ),
        env_name=env_name,
        timeout=data.get("timeout", 15),
    )
