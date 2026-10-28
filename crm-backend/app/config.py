from functools import lru_cache
from pathlib import Path

from pydantic_settings import BaseSettings, SettingsConfigDict

BASE_DIR = Path(__file__).resolve().parent.parent


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")

    app_name: str = "CRM Backend"
    debug: bool = True
    api_prefix: str = "/api/v1"

    database_url: str = f"sqlite:///{(BASE_DIR / 'data' / 'crm.db').as_posix()}"
    upload_dir: Path = BASE_DIR / "uploads"

    jwt_secret: str = "dev-secret-change-me"
    jwt_algorithm: str = "HS256"
    jwt_expire_minutes: int = 60 * 12

    default_timezone: str = "Asia/Shanghai"
    default_page_size: int = 20
    max_page_size: int = 100


@lru_cache
def get_settings() -> Settings:
    return Settings()
