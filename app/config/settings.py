from pathlib import Path

from dotenv import load_dotenv
from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict

from app.infrastructure.utils.decorators.singleton import singleton

load_dotenv()
devcontainer_env_path = (
    Path(__file__).parent.parent.parent / "podman" / "local" / "devcontainer.env"
)
if devcontainer_env_path.exists():
    load_dotenv(devcontainer_env_path, override=False)


@singleton
class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=[".env", str(devcontainer_env_path)]
        if devcontainer_env_path.exists()
        else ".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore",
    )
    APP_NAME: str = "genaro-app API"
    DESCRIPTION: str = "Backend service for genaro-app made with FastAPI"
    DEBUG: bool = True
    VERSION: str = "0.1.0"

    MONGODB_DATABASE: str = "genaro-app-mongodb"
    MONGODB_HOST: str = "mongodb"
    MONGODB_PORT: int = 27017
    MONGODB_USER: str = "admin"
    MONGODB_PASSWORD: str = "password123"
    mongodb_url_override: str | None = Field(default=None, alias="MONGODB_URL")

    @property
    def MONGODB_URL(self) -> str:
        if self.mongodb_url_override:
            return self.mongodb_url_override
        return (
            f"mongodb://{self.MONGODB_USER}:{self.MONGODB_PASSWORD}"
            f"@{self.MONGODB_HOST}:{self.MONGODB_PORT}/{self.MONGODB_DATABASE}?authSource=admin"
        )

    ALLOW_ORIGINS: str = "*"
    TIMEZONE: str = "UTC"

    # API settings
    API_PREFIX: str = "/api"
