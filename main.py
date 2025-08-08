from fastapi import FastAPI, HTTPException
from pydantic import BaseModel
from scripts.embedding_service import get_query_embedding
from scripts.firebase_service import search_fatwa_embeddings
from scripts.llm_service import generate_response_from_context
from fastapi.middleware.cors import CORSMiddleware

app = FastAPI()

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

class ChatRequest(BaseModel):
    message: str

class ChatResponse(BaseModel):
    response: str

@app.post("/chatbot", response_model=ChatResponse)
async def ask_chatbot(request: ChatRequest):
    try:
        # 1. Ambil input user
        user_message = request.message

        # 2. Embedding
        embedding_vector = get_query_embedding(user_message)

        # 3. Cari similarity di Firebase
        relevant_fatwa = await search_fatwa_embeddings(embedding_vector)

        # 4. Kirim ke LLM
        llm_response = await generate_response_from_context(user_message, relevant_fatwa)

        # 5. Kembalikan ke user
        return ChatResponse(response=llm_response)

    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))