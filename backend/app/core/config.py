from pydantic import model_validator
from pydantic_settings import BaseSettings

DEFAULT_SECRET_KEY = "dev_secret_key_change_in_production_min_32_chars!!"


class ConfigurationError(RuntimeError):
    """Raised when a production deployment has an insecure or missing configuration."""


class Settings(BaseSettings):
    # App
    APP_ENV: str = "development"
    DEBUG: bool = True
    ALLOWED_ORIGINS: str = "http://localhost:31368,http://192.168.0.144:31368"

    # Database – SQLite für lokale Entwicklung
    DATABASE_URL: str = "sqlite+aiosqlite:///./vera.db"

    # Wenn gesetzt, muss dieser Wert beim /auth/register mitgeschickt werden.
    # Leer lassen für lokale Entwicklung (offene Registrierung).
    # In Produktion immer setzen: openssl rand -hex 16
    REGISTRATION_SECRET: str = ""

    # Redis (optional – Celery deaktiviert wenn nicht gesetzt)
    REDIS_URL: str = "redis://localhost:6379/0"
    USE_CELERY: bool = False  # Im MVP deaktiviert

    # Security
    SECRET_KEY: str = DEFAULT_SECRET_KEY
    ALGORITHM: str = "HS256"
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 60
    REFRESH_TOKEN_EXPIRE_DAYS: int = 7

    # Frontend URL (für Einladungs- und Reset-Links)
    FRONTEND_URL: str = "http://localhost:31368"

    # E-Mail via SMTP (z.B. IONOS: smtp.ionos.de:587)
    SMTP_HOST: str = ""
    SMTP_PORT: int = 587
    SMTP_USER: str = ""
    SMTP_PASSWORD: str = ""
    SMTP_FROM_EMAIL: str = ""

    # Telegram (Phase 2)
    TELEGRAM_BOT_TOKEN: str = ""

    # Web Push / VAPID
    VAPID_PUBLIC_KEY: str = ""
    VAPID_PRIVATE_KEY: str = ""
    VAPID_CLAIMS_SUB: str = "mailto:admin@vera.app"

    @property
    def allowed_origins_list(self) -> list[str]:
        return [o.strip() for o in self.ALLOWED_ORIGINS.split(",")]

    model_config = {"env_file": ".env", "extra": "ignore"}

    @model_validator(mode="after")
    def _enforce_production_safety(self) -> "Settings":
        """Fail fast if APP_ENV=production runs with an insecure or missing config.

        Prevents the failure mode where a missing .env silently falls back to
        the well-known default SECRET_KEY (forgeable JWTs) and DEBUG=True
        (open /docs, verbose errors, SQL echo) in production.
        """
        if self.APP_ENV != "production":
            return self

        if self.SECRET_KEY == DEFAULT_SECRET_KEY or len(self.SECRET_KEY) < 32:
            raise ConfigurationError(
                "SECRET_KEY is missing or using the insecure default in a production "
                "environment (APP_ENV=production). Set a real SECRET_KEY (min. 32 chars, "
                "e.g. `openssl rand -hex 32`) in the environment or .env file."
            )

        self.DEBUG = False
        return self


settings = Settings()
