from pydantic_settings import BaseSettings, SettingsConfigDict
from typing import Optional, List
from app.core.constants import API_V1_STR, ModelProvider

class Settings(BaseSettings):
    # App Settings
    APP_NAME: str = "MCP ChatBot"
    DEBUG: bool = True
    VERSION: str = "1.0.0"
    API_V1_STR: str = API_V1_STR
    SECRET_KEY: str = "dev-secret-key-change-in-production-at-least-32-chars"
    
    # Environment
    ENVIRONMENT: str = "development"
    
    # Database
    DATABASE_URL: str = "sqlite+aiosqlite:///./test.db"
    REDIS_URL: str = "redis://localhost:6379/0"
    
    # LLM Settings
    LLM_PROVIDER: ModelProvider = ModelProvider.DEEPSEEK
    
    OPENAI_API_KEY: Optional[str] = None
    DEEPSEEK_API_KEY: Optional[str] = None
    ANTHROPIC_API_KEY: Optional[str] = None
    OLLAMA_BASE_URL: str = "http://localhost:11434"
    
    # Auth
    JWT_ALGORITHM: str = "HS256"
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 1440
    
    # MCP Settings
    MCP_SERVER_COMMAND: str = "python"
    MCP_SERVER_ARGS: List[str] = []
    
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

settings = Settings()
