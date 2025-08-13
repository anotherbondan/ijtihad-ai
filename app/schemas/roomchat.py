from pydantic import BaseModel
from uuid import UUID
from datetime import datetime

class RoomChatBase(BaseModel):
    room_name: str

class RoomChatResponse(RoomChatBase):
    id: UUID
    owner_id: UUID           
    created_at: datetime

    class Config:
        orm_mode = True
