from enum import StrEnum
from pathlib import Path

from pydantic_settings import BaseSettings, SettingsConfigDict

DOTENV_PATH = Path(__file__).resolve().parent.parent.parent / ".env"

class EnvironmentOption(StrEnum):
    DEVELOPMENT = "development"
    PRODUCTION = "production"
    
class LogLevelOption(StrEnum):
    DEBUG = "DEBUG"
    INFO = "INFO"
    WARNING = "WARNING"
    ERROR = "ERROR"
    CRITICAL = "CRITICAL"

class AppSettings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=DOTENV_PATH,
        env_file_encoding="utf-8",
        env_ignore_empty=True, 
        populate_by_name=True,
        env_prefix="APP_", 
        extra="ignore", 
    )
    
    NAME: str = "Orchestrator Service"
    DESCRIPTION: str = "Orchestrator Service for managing legislative voting workflows."
    VERSION: str = "0.1.0"
    ENVIRONMENT: EnvironmentOption = EnvironmentOption.DEVELOPMENT
    DEBUG: bool = False
    HOST: str = "0.0.0.0"
    PORT: int = 8000

class DatabaseSettings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=DOTENV_PATH,
        env_file_encoding="utf-8",
        env_ignore_empty=True, 
        populate_by_name=True,
        env_prefix="DB_", 
        extra="ignore", 
    )
    
    HOST: str = "localhost"
    PORT: int = 5432
    NAME: str = "orchestrator_db"
    USER: str = "orchestrator_user"
    PASSWORD: str = "orchestrator_password"
    POOL_MIN_SIZE: int = 5
    POOL_MAX_SIZE: int = 20
    POOL_TIMEOUT_SECONDS: int = 5
    POOL_RECYCLE_SECONDS: int = 1800
    STATEMENT_TIMEOUT_MS: int = 5000
    
    @property
    def URI(self) -> str:
        return (
            f"postgresql+asyncpg://{self.USER}:{self.PASSWORD}"
            f"@{self.HOST}:{self.PORT}/{self.NAME}"
        )

class SecuritySettings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=DOTENV_PATH,
        env_file_encoding="utf-8",
        env_ignore_empty=True, 
        populate_by_name=True,
        env_prefix="", 
        extra="ignore", 
    )
    
    ANTI_REPLAY_WINDOW_SECONDS: int = 60
    SESSION_COOKIE_NAME: str = "session_id"
    SESSION_EXPIRY_SECONDS: int = 28800     
    ARGON2_TIME_COST: int = 2
    ARGON2_MEMORY_COST: int = 65536
    ARGON2_PARALLELISM: int = 2
    CORS_ALLOWED_ORIGINS: str = "http://localhost:3000"
    EXPECTED_APK_HASH: str = ""

    @property
    def CORS_ALLOWED_ORIGINS_LIST(self) -> list[str]:
        return [origin.strip() for origin in self.CORS_ALLOWED_ORIGINS.split(",") if origin.strip()]

class LoggingSettings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=DOTENV_PATH,
        env_file_encoding="utf-8",
        env_ignore_empty=True, 
        populate_by_name=True,
        env_prefix="LOG_", 
        extra="ignore", 
    )

    LEVEL: LogLevelOption = LogLevelOption.INFO
    SERVICE_NAME: str = "orchestrator"

class BlockchainSettings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=DOTENV_PATH,
        env_file_encoding="utf-8",
        env_ignore_empty=True, 
        populate_by_name=True,
        extra="ignore", 
    )

    ORCHESTRATOR_WALLET_PRIVATE_KEY: str = ""
    POLYGON_AMOY_RPC_URL: str = ""
    CONTRACT_ADDRESS: str = ""
    ABI_PATH: str = "contracts/abi.json"

class Settings(BaseSettings):
    app: AppSettings = AppSettings()
    db: DatabaseSettings = DatabaseSettings()
    security: SecuritySettings = SecuritySettings()
    logging: LoggingSettings = LoggingSettings()
    blockchain: BlockchainSettings = BlockchainSettings()

settings: Settings = Settings()