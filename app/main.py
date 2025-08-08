from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from app.api import halalscan, chatbot
from tortoise.contrib.fastapi import register_tortoise
from app.db_config import TORTOISE_ORM

app = FastAPI()

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
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

@app.get("/")
async def root():
    return {"message": "API is running"}


