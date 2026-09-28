from pathlib import Path

from dotenv import load_dotenv
from limits import parse_many
from pydantic import Field, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

from app.infrastructure.utils.decorators.singleton import singleton

load_dotenv()
podman_local_dir = Path(__file__).parent.parent.parent / "podman" / "local"
podman_local_env_path = podman_local_dir / ".env"
devcontainer_env_path = podman_local_dir / "devcontainer.env"
if devcontainer_env_path.exists():
    load_dotenv(devcontainer_env_path, override=False)

# Env files read by Settings, later ones taking priority. podman/local/.env is
# included so its values (e.g. AUTH=False) also apply when running on the host.
env_files = [
    str(path)
    for path in (podman_local_env_path, Path(".env"), devcontainer_env_path)
    if path.exists()
]


@singleton
class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=env_files,
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

    # Rate limit shared by every endpoint per client IP (docs routes exempt),
    # in slowapi/limits notation, e.g. "10/minute", "100/hour".
    RATE_LIMIT: str = "10/minute"
    RATE_LIMIT_ENABLED: bool = True

    @field_validator("RATE_LIMIT")
    @classmethod
    def validate_rate_limit(cls, value: str) -> str:
        """Fail at startup on a malformed limit instead of on every request."""
        parse_many(value)
        return value

    # API key authentication (header X-API-Key). Disable only for local dev.
    AUTH: bool = True
    API_KEY: str | None = None

    # iTunes Search API
    ITUNES_BASE_URL: str = "https://itunes.apple.com"
    ITUNES_TIMEOUT_SECONDS: float = 10.0

    # Bulk podcast ingestion: podcasts processed at the same time.
    PODCAST_INGEST_CONCURRENCY: int = 5

    # Podcast export: podcasts read from the database per batch. At least 1,
    # since MongoDB treats a limit of 0 as no limit.
    PODCAST_EXPORT_BATCH_SIZE: int = Field(default=500, ge=1)

    # Podcast artwork path
    ARTWORK_STORAGE_DIR: str = "media/artwork"
    ARTWORK_TIMEOUT_SECONDS: float = 10.0
    ARTWORK_PALETTE_SIZE: int = 5
