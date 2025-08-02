from fastapi import FastAPI, Request, Form
from fastapi.responses import HTMLResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates

app = FastAPI()
templates = Jinja2Templates(directory="templates")
app.mount("/static", StaticFiles(directory="static"), name="static")

@app.get("/", response_class=HTMLResponse)
async def read_home_page(request: Request):
    return templates.TemplateResponse("index.html", {"request": request})

@app.get("/chatbot", response_class=HTMLResponse)
async def read_chatbot_page(request: Request):
    return templates.TemplateResponse("Chatbot/index.html", {"request": request})