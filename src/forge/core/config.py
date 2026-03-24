"""Application configuration using pydantic-settings."""

from functools import lru_cache
from typing import Annotated

from pydantic import AnyHttpUrl, BeforeValidator, computed_field
from pydantic_settings import BaseSettings, SettingsConfigDict


def parse_cors_origins(v: str | list[str]) -> list[str]:
    """Parse CORS origins from string or list."""
    if isinstance(v, str):
        return [origin.strip() for origin in v.split(",") if origin.strip()]
    return v


class Settings(BaseSettings):
    """Application settings loaded from environment variables."""

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=True,
        extra="ignore",
    )

    PROJECT_NAME: str = "Forge"
    API_V1_PREFIX: str = "/api/v1"
    DEBUG: bool = False

    # Database
    # Provide a connection URL via environment in the form:
    # postgresql+asyncpg://<user>:<password>@<host>:<port>/<database>
    DATABASE_URL: str = ""

    # Security
    # Set a strong random key in production.
    SECRET_KEY: str = ""
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 60
    REFRESH_TOKEN_EXPIRE_DAYS: int = 7
    INVITATION_TOKEN_EXPIRE_DAYS: int = 7
    PASSWORD_RESET_TOKEN_EXPIRE_HOURS: int = 24
    ALGORITHM: str = "HS256"

    # CORS
    CORS_ORIGINS: Annotated[list[str], BeforeValidator(parse_cors_origins)] = [
        "http://localhost:3000"
    ]

    # Email (Resend)
    RESEND_API_KEY: str = ""
    EMAIL_FROM_ADDRESS: str = "noreply@kamilimu.org"
    EMAIL_FROM_NAME: str = "KamiLimu Forge"

    # Frontend URL for email links
    FRONTEND_URL: AnyHttpUrl = "http://localhost:3000"  # type: ignore[assignment]

    # Password requirements
    PASSWORD_MIN_LENGTH: int = 8
    PASSWORD_REQUIRE_UPPERCASE: bool = True
    PASSWORD_REQUIRE_LOWERCASE: bool = True
    PASSWORD_REQUIRE_DIGIT: bool = True

    @computed_field  # type: ignore[prop-decorator]
    @property
    def database_url_sync(self) -> str:
        """Return synchronous database URL for Alembic migrations."""
        return self.DATABASE_URL.replace("+asyncpg", "")


@lru_cache
def get_settings() -> Settings:
    """Return cached settings instance."""
    return Settings()


settings = get_settings()
