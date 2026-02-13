from pydantic import BaseModel, ConfigDict, Field
from typing import List, Optional, Any

class ChatMessage(BaseModel):
    model_config = ConfigDict(populate_by_name=True)
    
    role: str = Field(..., pattern="^(user|assistant|system|tool)$")
    content: str
    name: Optional[str] = None
    tool_call_id: Optional[str] = None

class ChatRequest(BaseModel):
    messages: List[ChatMessage]
    model: Optional[str] = "gpt-4o"

class ChatResponse(BaseModel):
    id: str
    object: str = "chat.completion"
    created: int
    model: str
    choices: List[dict]
    usage: Optional[dict] = None
