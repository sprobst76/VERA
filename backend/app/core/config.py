from pydantic_settings import BaseSettings


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
    SECRET_KEY: str = "dev_secret_key_change_in_production_min_32_chars!!"
    ALGORITHM: str = "HS256"
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 60
    REFRESH_TOKEN_EXPIRE_DAYS: int = 7

    # SendGrid (Phase 2)
    SENDGRID_API_KEY: str = ""
    SENDGRID_FROM_EMAIL: str = "vera@yourdomain.de"

    # Telegram (Phase 2)
    TELEGRAM_BOT_TOKEN: str = ""

    @property
    def allowed_origins_list(self) -> list[str]:
        return [o.strip() for o in self.ALLOWED_ORIGINS.split(",")]

    model_config = {"env_file": ".env", "extra": "ignore"}


settings = Settings()
