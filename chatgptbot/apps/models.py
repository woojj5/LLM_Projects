from pydantic import BaseModel
from typing import List, Optional

class Message(BaseModel):
    role: str
    content: str

class ChatRequest(BaseModel):
    session_id: str
    messages: List[Message]
    top_k: int = 3
    temperature: float = 0.7

class ChatResponse(BaseModel):
    output: str
    citations: Optional[list] = None
