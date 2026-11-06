"""Configuration centralisée — chargée depuis .env."""
from functools import lru_cache

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    APP_ENV: str = "dev"
    APP_NAME: str = "Mada Settlement Lab"
    APP_SECRET_KEY: str = "dev-only-change-me"

    DATABASE_URL: str = "postgresql+psycopg://msl:msl@localhost:5432/msl"

        # JWT
    JWT_SECRET_KEY: str = "dev-only-secret"
    JWT_ALGORITHM: str = "HS256"
    JWT_EXPIRE_MINUTES: int = 60

        # MinIO
    MINIO_ENDPOINT: str = "minio:9000"
    MINIO_ROOT_USER: str = "minioadmin"
    MINIO_ROOT_PASSWORD: str = "minioadmin"
    MINIO_BUCKET: str = "submissions"


@lru_cache
def get_settings() -> Settings:
    return Settings()
