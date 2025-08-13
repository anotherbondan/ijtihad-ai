from app.services.embedding_service import get_query_embedding
from app.services.firebase_service import search_fatwa_embeddings
from app.services.llm_service import generate_response_from_context
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

        embedding_vector = get_query_embedding(user_message)

        relevant_fatwa = await search_fatwa_embeddings(embedding_vector)

        llm_response = await generate_response_from_context(user_message, relevant_fatwa)

        return ChatResponse(response=llm_response)

    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))