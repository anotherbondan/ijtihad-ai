from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from api import halalscan

app = FastAPI()

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(halalscan.router, prefix="/halal-scan", tags=["HalalScan"])

@app.get("/")
def root():
    return {"message": "API is running"}


