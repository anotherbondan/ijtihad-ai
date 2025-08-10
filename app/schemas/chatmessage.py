from pydantic import BaseModel
from uuid import UUID
from datetime import datetime
from typing import Optional

class ChatMessageBase(BaseModel):
    message: str
    sender_type: str   
    sender_id: Optional[UUID] = None 

class ChatMessageResponse(ChatMessageBase):
    id: int
    room_id: UUID
    created_at: datetime

    class Config:
        orm_mode = True
