from functools import lru_cache
from pathlib import Path
from typing import Literal

import yaml
from pydantic import SecretStr
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    env: Literal["dev", "prod", "test"] = "dev"
    data_dir: Path = Path("data")
    warehouse_path: Path = Path("data/warehouse.duckdb")
    http_contact: str = ""
    pseudonym_salt: SecretStr = SecretStr("")
    llm_api_key: SecretStr = SecretStr("")
    llm_model: str = ""
    supabase_url: str = ""
    supabase_service_key: SecretStr = SecretStr("")
    mlflow_tracking_uri: str = "./mlruns"

    model_config = SettingsConfigDict(env_file=".env", extra="ignore")


@lru_cache
def get_settings() -> Settings:
    # Environment and dotenv values override the optional YAML defaults.
    env = Settings().env
    path = Path(f"config/settings.{env}.yaml")
    if not path.exists():
        return Settings()
    with path.open(encoding="utf-8") as file:
        defaults = yaml.safe_load(file)
    if defaults is None:
        defaults = {}
    if not isinstance(defaults, dict):
        raise ValueError(f"Expected a mapping in {path}")
    return Settings.model_validate({**defaults, **Settings().model_dump(exclude_unset=True)})
