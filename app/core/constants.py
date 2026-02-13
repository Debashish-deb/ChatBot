from enum import Enum

class ModelProvider(str, Enum):
    OPENAI = "openai"
    ANTHROPIC = "anthropic"
    OLLAMA = "ollama"
    DEEPSEEK = "deepseek"

DEFAULT_MODEL_MAP = {
    ModelProvider.OPENAI: "gpt-4o",
    ModelProvider.ANTHROPIC: "claude-3-5-sonnet-20240620",
    ModelProvider.OLLAMA: "llama3",
    ModelProvider.DEEPSEEK: "deepseek-chat"
}

API_V1_STR = "/api/v1"
