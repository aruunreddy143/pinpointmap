from functools import lru_cache
from typing import Literal

from pydantic import field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

_DEV_SECRET = "dev-only-change-me"  # noqa: S105 (a marker, rejected outside development)


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_prefix="PINPOINT_", env_file=".env", extra="ignore")

    environment: Literal["development", "test", "production"] = "development"
    database_url: str = "postgresql+psycopg://pinpoint:pinpoint_dev_only@localhost:5432/pinpoint"
    test_database_url: str = "postgresql+psycopg://pinpoint:pinpoint_dev_only@localhost:5432/pinpoint_test"
    secret_key: str = _DEV_SECRET
    public_base_url: str = "http://localhost:5173"
    cors_origins: list[str] = ["http://localhost:5173"]

    @field_validator("secret_key")
    @classmethod
    def _no_default_secret_in_production(cls, v: str, info) -> str:  # noqa: ANN001
        if info.data.get("environment") == "production" and (v == _DEV_SECRET or len(v) < 32):
            raise ValueError(
                "PINPOINT_SECRET_KEY must be a random value of at least 32 characters in production"
            )
        return v


@lru_cache
def get_settings() -> Settings:
    return Settings()
