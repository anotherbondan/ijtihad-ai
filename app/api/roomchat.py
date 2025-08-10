from fastapi import APIRouter, HTTPException
from app.schemas.roomchat import RoomChatResponse
from app.schemas.chatmessage import ChatMessageResponse
from app.crud.roomchat import get_rooms_by_owner
from app.crud.chatmessage import get_messages_by_room
from typing import List


# Define API Router
router = APIRouter()

@router.get("/{room_id}/messages", response_model=List[ChatMessageResponse])
async def get_room_messages(room_id):
    try:
        messages = get_messages_by_room(room_id)
        return messages
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@router.get("/user/{user_id}", response_model=List[RoomChatResponse])
async def get_rooms_by_user_id(user_id):
    try: 
        rooms = get_rooms_by_owner(user_id)
        return rooms
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))