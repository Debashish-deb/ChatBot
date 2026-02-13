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
    model: Optional[str] = None
    conversation_id: Optional[str] = None
    temperature: Optional[float] = 0.7

class StreamChatRequest(ChatRequest):
    pass

class ChatResponse(BaseModel):
    id: str
    object: str = "chat.completion"
    created: int
    model: str
    choices: List[dict]
    usage: Optional[dict] = None

class UserBase(BaseModel):
    email: str
    full_name: Optional[str] = None

class UserCreate(UserBase):
    password: str

class UserResponse(UserBase):
    id: str
    is_active: bool
    tier: str
    
    model_config = ConfigDict(from_attributes=True)

class Token(BaseModel):
    access_token: str
    token_type: str

class TokenData(BaseModel):
    email: Optional[str] = None
