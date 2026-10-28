# -*- coding: utf-8 -*-
from functools import lru_cache
from pathlib import Path

from pydantic import model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

BASE_DIR = Path(__file__).resolve().parent.parent

# 仅允许在 debug=True（本地开发）时作为回退；非 debug 启动必须覆盖。
WEAK_JWT_DEFAULT = "dev-secret-change-me"
DEFAULT_CORS_ORIGINS = "http://localhost:5173,http://127.0.0.1:5173"


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")

    app_name: str = "CRM Backend"
    debug: bool = True
    api_prefix: str = "/api/v1"

    database_url: str = f"sqlite:///{(BASE_DIR / 'data' / 'crm.db').as_posix()}"
    upload_dir: Path = BASE_DIR / "uploads"

    # 环境变量：JWT_SECRET
    jwt_secret: str = WEAK_JWT_DEFAULT
    jwt_algorithm: str = "HS256"
    jwt_expire_minutes: int = 60 * 12

    # 逗号分隔前端源白名单（环境变量 CORS_ORIGINS）；禁止 "*" + credentials。
    cors_origins: str = DEFAULT_CORS_ORIGINS

    default_timezone: str = "Asia/Shanghai"
    default_page_size: int = 20
    max_page_size: int = 100

    @model_validator(mode="after")
    def reject_insecure_defaults_outside_debug(self) -> "Settings":
        if self.debug:
            return self
        if not self.jwt_secret or self.jwt_secret == WEAK_JWT_DEFAULT:
            raise ValueError(
                "JWT_SECRET must be set to a strong non-default value when debug=false"
            )
        if len(self.jwt_secret) < 32:
            raise ValueError("JWT_SECRET must be at least 32 characters when debug=false")
        origins = self.cors_origin_list()
        if not origins or "*" in origins:
            raise ValueError(
                "CORS_ORIGINS must be an explicit whitelist (no *) when debug=false"
            )
        return self

    def cors_origin_list(self) -> list[str]:
        return [part.strip() for part in self.cors_origins.split(",") if part.strip()]


@lru_cache
def get_settings() -> Settings:
    return Settings()
