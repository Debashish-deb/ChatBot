from pydantic_settings import BaseSettings, SettingsConfigDict
from typing import Optional, List
from app.core.constants import API_V1_STR, ModelProvider

class Settings(BaseSettings):
    APP_NAME: str = "MCP ChatBot"
    DEBUG: bool = True
    VERSION: str = "0.1.0"
    API_V1_STR: str = API_V1_STR
    
    # LLM Settings
    LLM_PROVIDER: ModelProvider = ModelProvider.DEEPSEEK
    
    OPENAI_API_KEY: Optional[str] = None
    DEEPSEEK_API_KEY: Optional[str] = None
    ANTHROPIC_API_KEY: Optional[str] = None
    OLLAMA_BASE_URL: str = "http://localhost:11434"
    
    # MCP Settings
    MCP_SERVER_COMMAND: str = "python"
    MCP_SERVER_ARGS: List[str] = []
    
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

settings = Settings()
