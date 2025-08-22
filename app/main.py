from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from app.api import ghararmaysir, halalscan, chatbot, chatmessage, user, roomchat
from tortoise.contrib.fastapi import register_tortoise
from app.db_config import TORTOISE_ORM
import os

app = FastAPI()

origins =  os.getenv("ALLOWED_ORIGINS", "https://ijtihad.vercel.app").split(",")

app.add_middleware(
    CORSMiddleware,
    allow_origins=origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

register_tortoise(
    app,
    config=TORTOISE_ORM,
    generate_schemas=False, 
    add_exception_handlers=True,
)

app.include_router(halalscan.router, prefix="/halal-scan", tags=["HalalScan"])
app.include_router(chatbot.router, prefix="/chatbot", tags=["Chatbot"])
app.include_router(user.router, prefix="/users", tags=["User"])
app.include_router(roomchat.router, prefix="/rooms", tags=["RoomChat"])
app.include_router(chatmessage.router, prefix="/messages", tags=["Message"])
app.include_router(ghararmaysir.router, prefix="/gharar-maysir", tags=["GhararMaysir"])

@app.get("/")
async def root():
    return {"message": "Server is running"}
