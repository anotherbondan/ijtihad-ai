from typing import List, Optional
from app.models import ChatMessage
from uuid import UUID

async def get_messages_by_room(room_id: UUID) -> List[ChatMessage]:
    return await ChatMessage.filter(room_id=room_id).all()

async def create_message(room_id: UUID, sender_type: str, sender_id: Optional[UUID], message: str) -> ChatMessage:
    chat_message = await ChatMessage.create(
        room_id=room_id,
        sender_type=sender_type,
        sender_id=sender_id,
        message=message
    )
    return chat_message