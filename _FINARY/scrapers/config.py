"""Configuration loaded from environment / .env file."""

from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    database_url: str = "postgresql://finary:finary_dev@localhost:5433/finary"
    redis_url: str = "redis://localhost:6380"
    finnhub_api_key: str = ""
    master_password: str = ""

    model_config = {"env_file": ".env", "env_file_encoding": "utf-8"}


settings = Settings()
