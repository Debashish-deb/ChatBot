from pydantic import BaseModel, ConfigDict, Field
from typing import List, Optional, Any

class ChatMessage(BaseModel):
    model_config = ConfigDict(populate_by_name=True)
    
    role: str = Field(..., pattern="^(user|assistant|system|tool)$")
    content: Union[str, List[ContentPart]]
    name: Optional[str] = None
    tool_calls: Optional[List[Any]] = None
    tool_call_id: Optional[str] = None

class ChatRequest(BaseModel):
    messages: List[ChatMessage]
    model: Optional[str] = None
    conversation_id: Optional[str] = None
    temperature: Optional[float] = 0.7
    stream: Optional[bool] = False

class StreamChatRequest(ChatRequest):
    stream: bool = True

class ChatResponse(BaseModel):
    id: str
    object: str = "chat.completion"
    created: int
    model: str
    choices: List[Dict[str, Any]]
    usage: Dict[str, int] = None

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
