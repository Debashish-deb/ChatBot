from pydantic import BaseModel
from typing import Optional

class ChatSession(BaseModel):
    id: str
    user_id: str
    metadata: Optional[dict] = None
