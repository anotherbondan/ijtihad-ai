from typing import List
from app.models import ChatMessage
from uuid import UUID

async def get_messages_by_room(room_id: UUID) -> List[ChatMessage]:
    return await ChatMessage.filter(room_id=room_id).all()