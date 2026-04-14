from pydantic_settings import BaseSettings
from pathlib import Path


class Settings(BaseSettings):
    WORKSPACE_STORAGE_DIR: Path = Path("/home/nixuser/ree/workspaces")

    class Config:
        env_file = ".env"


service_settings = Settings()
