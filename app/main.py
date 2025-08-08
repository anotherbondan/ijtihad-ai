from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from api import halalscan, chatbot
from tortoise.contrib.fastapi import register_tortoise

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
    db_url="postgres://postgres:postgres@localhost:5432/ijtihad",
    modules={"models": ["app.models"]},  # path ke module model kamu
    generate_schemas=False,  # jangan auto generate di production
    add_exception_handlers=True,
)

app.include_router(halalscan.router, prefix="/halal-scan", tags=["HalalScan"])
app.include_router(chatbot.router, prefix="/chatbot", tags=["Chatbot"])

@app.get("/")
def root():
    return {"message": "API is running"}


