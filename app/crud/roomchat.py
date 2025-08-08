from typing import List
from app.models import RoomChat
from uuid import UUID

async def get_rooms_by_owner(owner_id: UUID) -> List[RoomChat]:
    return await RoomChat.filter(owner_id=owner_id).all()

async def create_room(owner_id: UUID, room_name: str) -> RoomChat:
    return await RoomChat.create(owner_id=owner_id, room_name=room_name)
