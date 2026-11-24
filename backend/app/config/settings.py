"""Configuration de l'application HERA V2."""

from functools import lru_cache
from typing import Literal

from pydantic import PostgresDsn, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Configuration principale de l'application."""

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
    )

    # Application
    app_name: str = "HERA V2 API"
    app_version: str = "2.0.0"
    debug: bool = False
    environment: Literal["development", "testing", "production"] = "development"

    # API
    api_v1_prefix: str = "/api/v1"

    # Database
    database_url: PostgresDsn
    database_echo: bool = False

    # Security
    secret_key: str
    algorithm: str = "HS256"
    access_token_expire_minutes: int = 30
    refresh_token_expire_days: int = 7

    # Authentication Provider
    # Options: "local", "saml", "oidc"
    auth_provider: Literal["local", "saml", "oidc"] = "local"

    # SAML Configuration (Renater/Shibboleth)
    saml_enabled: bool = False
    saml_metadata_url: str | None = None
    saml_entity_id: str | None = None
    saml_acs_url: str | None = None
    saml_sls_url: str | None = None

    # OIDC Configuration
    oidc_enabled: bool = False
    oidc_provider_url: str | None = None
    oidc_client_id: str | None = None
    oidc_client_secret: str | None = None
    oidc_redirect_uri: str | None = None

    # CORS
    cors_origins: list[str] = ["http://localhost:3000", "http://localhost:5173"]

    # Logging
    log_level: str = "INFO"

    @field_validator("cors_origins", mode="before")
    @classmethod
    def parse_cors_origins(cls, v: str | list[str]) -> list[str]:
        if isinstance(v, str):
            return [origin.strip() for origin in v.split(",")]
        return v


@lru_cache
def get_settings() -> Settings:
    """Retourne les paramètres de configuration (cached)."""
    return Settings()
