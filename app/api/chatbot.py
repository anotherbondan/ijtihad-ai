from app.services.llm_service import generate_response_from_context, generate_response_with_search
from app.crud.roomchat import get_rooms_by_owner
from app.schemas.roomchat import RoomChatResponse
from pydantic import BaseModel
from fastapi import APIRouter, HTTPException 
from typing import List
from uuid import UUID

router = APIRouter()

class ChatRequest(BaseModel):
    message: str

class ChatResponse(BaseModel):
    response: str

@router.post("/", response_model=ChatResponse)
async def ask_chatbot(request: ChatRequest):
    try:
        user_message = request.message

        llm_response = await generate_response_with_search(user_message)

        return ChatResponse(response=llm_response)

    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))