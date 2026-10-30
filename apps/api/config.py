"""Configuration centralisée — chargée depuis .env."""
from functools import lru_cache

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    APP_ENV: str = "dev"
    APP_NAME: str = "Mada Settlement Lab"
    APP_SECRET_KEY: str = "dev-only-change-me"

    DATABASE_URL: str = "postgresql+psycopg://msl:msl@localhost:5432/msl"


@lru_cache
def get_settings() -> Settings:
    return Settings()
