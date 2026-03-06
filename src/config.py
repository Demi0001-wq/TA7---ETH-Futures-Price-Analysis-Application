import os
from pydantic_settings import BaseSettings, SettingsConfigDict
from typing import Optional

class Settings(BaseSettings):
    # Binance Config - using fstream for futures
    BINANCE_WS_URL: str = "wss://fstream.binance.com/ws"
    BINANCE_API_KEY: Optional[str] = None
    BINANCE_API_SECRET: Optional[str] = None
    
    # Assets to monitor (e.g., BTCUSDT as base, ETHUSDT as target)
    BASE_SYMBOL: str = "BTCUSDT"
    TARGET_SYMBOL: str = "ETHUSDT"

    # Admin credentials for dashboard
    ADMIN_USERNAME: str = "admin"
    ADMIN_PASSWORD: str = "password"

    # SQLite database file path
    DATABASE_URL: str = "sqlite:///./data/alerts.db"

    # thresholds for our math
    ALERT_THRESHOLD_PERCENT: float = 1.0
    ALERT_WINDOW_MINUTES: int = 60
    BETA_WINDOW_HOURS: int = 24

    # Telegram bot info (leave empty if not using)
    TELEGRAM_BOT_TOKEN: Optional[str] = None
    TELEGRAM_CHAT_ID: Optional[str] = None

    # security keys for jwt and encryption
    JWT_SECRET: str = "super_secret_key"
    JWT_ALGORITHM: str = "HS256"
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 30

    # Key for encrypted state saving (generate with Fernet.generate_key().decode())
    ENCRYPTION_KEY: Optional[str] = None

    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")

settings = Settings()
