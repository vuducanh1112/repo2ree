from pathlib import Path

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    WORKSPACE_STORAGE_DIR: Path = Path(".repo2ree/workspaces")
    REVIEWS_STORAGE_DIR: Path = Path(".repo2ree/reviews")


service_settings = Settings()
