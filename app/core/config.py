"""Configuration de l'application, lue depuis les variables d'environnement (12-factor)."""

from functools import lru_cache
from zoneinfo import ZoneInfo

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    app_name: str = "La Grande Cinéma - API"
    database_url: str = "sqlite:///./grande_cinema.db"
    jwt_secret: str = "change-me-in-production"  # noqa: S105 - surchargé par JWT_SECRET en production
    jwt_algorithm: str = "HS256"
    jwt_expire_minutes: int = 60
    cors_origins: str = "http://localhost:5173"
    max_seats_per_booking: int = 10
    timezone: str = "Europe/Paris"

    @property
    def tz(self) -> ZoneInfo:
        return ZoneInfo(self.timezone)

    @property
    def cors_origin_list(self) -> list[str]:
        return [o.strip() for o in self.cors_origins.split(",") if o.strip()]

    @property
    def sqlalchemy_url(self) -> str:
        # Render / Neon fournissent parfois "postgres://", non reconnu par SQLAlchemy 2.
        if self.database_url.startswith("postgres://"):
            return self.database_url.replace("postgres://", "postgresql://", 1)
        return self.database_url


@lru_cache
def get_settings() -> Settings:
    return Settings()
