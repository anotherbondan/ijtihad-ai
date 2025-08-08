from services.embedding_service import get_query_embedding
from services.firebase_service import search_fatwa_embeddings
from services.llm_service import generate_response_from_context
from pydantic import BaseModel
from fastapi import APIRouter, HTTPException

router = APIRouter()

class ChatRequest(BaseModel):
    message: str

class ChatResponse(BaseModel):
    response: str

@router.post("/chatbot", response_model=ChatResponse)
async def ask_chatbot(request: ChatRequest):
    try:
        user_message = request.message

        embedding_vector = get_query_embedding(user_message)

        relevant_fatwa = await search_fatwa_embeddings(embedding_vector)

        llm_response = await generate_response_from_context(user_message, relevant_fatwa)

        return ChatResponse(response=llm_response)

    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
    