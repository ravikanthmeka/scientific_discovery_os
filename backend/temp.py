from typing import Optional
from pydantic import BaseModel

class ChatRequest(BaseModel):
    message: str
    token: Optional[str] = None
