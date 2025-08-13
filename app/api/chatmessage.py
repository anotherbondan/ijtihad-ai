from fastapi import APIRouter, HTTPException 
from app.schemas.chatmessage import ChatMessageResponse, ChatMessageBase
from app.crud.chatmessage import create_message

# Define API Router
router = APIRouter()

@router.post("/{room_id}", response_model=ChatMessageResponse) 
async def create_new_message(room_id, body: ChatMessageBase):
    try:
        chat_message = await create_message(room_id, body.sender_type, body.sender_id, body.message)
        return chat_message
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
