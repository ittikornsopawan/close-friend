from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_prefix="CF_API_", env_file=".env")

    redis_url: str = "redis://localhost:6379/0"
    database_url: str = "postgresql+psycopg://close_friend:close_friend@localhost:5432/close_friend"
    cors_origins: list[str] = ["http://localhost:3000"]


settings = Settings()
