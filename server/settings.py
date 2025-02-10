from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine
from sqlalchemy.ext.declarative import declarative_base
from pydantic_settings import BaseSettings, SettingsConfigDict
from functools import lru_cache
from enum import Enum
import os
from dotenv import load_dotenv

# Load environment variables first
env = os.getenv("APP_ENV", "local")
env_file = f".env.{env}"
load_dotenv(env_file, override=True)

# ---- Environment variables (Secret keys) ----
JWE_SECRET_KEY = os.getenv("JWE_SECRET_KEY")
if JWE_SECRET_KEY is None:
    raise ValueError("JWE_SECRET_KEY environment variable is not set")
JWE_SECRET_KEY = JWE_SECRET_KEY.encode()

ARGON2_SECRET_KEY = os.getenv("ARGON2_SECRET_KEY")
if ARGON2_SECRET_KEY is None:
    raise ValueError("ARGON2_SECRET_KEY environment variable is not set")

DISPATCH_ADMIN_KEY = os.getenv("DISPATCH_ADMIN_KEY")
if DISPATCH_ADMIN_KEY is None:
    raise ValueError("DISPATCH_ADMIN_KEY environment variable is not set")
# ---------------------------------------------

# Define EnvironmentType before using it
class EnvironmentType(str, Enum):
    LOCAL = "local"
    DEVELOPMENT = "development"
    PRODUCTION = "production"

class Settings(BaseSettings):
    # App settings
    app_env: EnvironmentType = EnvironmentType.LOCAL
    debug: bool = True
    host: str = "0.0.0.0"
    port: int = 8000
    log_level: str = "INFO"

    # API settings
    api_version: str = "v1"
    api_prefix: str = "/api/v1"

    # Database settings
    db_port: int = int(os.getenv("DB_PORT", 3306))
    db_user_primary: str = os.getenv("DB_USER_PRIMARY", "")
    db_password_primary: str = os.getenv("DB_PASSWORD_PRIMARY", "")
    db_database_primary: str = os.getenv("DB_DATABASE_PRIMARY", "")
    db_host: str = os.getenv("DB_HOST", "localhost")

    @property
    def primary_db_url(self) -> str:
        return (
            f"mysql+aiomysql://{self.db_user_primary}:{self.db_password_primary}"
            f"@{self.db_host}:{self.db_port}/{self.db_database_primary}"
        )

    model_config = SettingsConfigDict(
        case_sensitive=True,
        env_file_encoding="utf-8",
        extra="allow",
        env_nested_delimiter="__",
    )

@lru_cache()
def get_settings() -> Settings:
    """Get settings instance with environment-based configuration"""
    try:
        settings = Settings()
        print("Settings loaded successfully")
        return settings
    except Exception as e:
        print(f"Error loading settings: {str(e)}")
        return Settings()

# Create settings instance
settings = get_settings()

# Create a base class for your models
Base = declarative_base()

# Create the database engine using the settings instance
primary_engine = create_async_engine(
    settings.primary_db_url,
    pool_size=8,
    pool_recycle=21600,
    echo=False, 
)

# Create a session factory function for the primary database
def PrimarySessionLocal():
    return AsyncSession(
        bind=primary_engine,
        expire_on_commit=False,
    )

# Dependency injection for the primary database
async def get_primary_db() -> AsyncSession:
    async with PrimarySessionLocal() as session:
        try:
            yield session
        finally:
            await session.close()
