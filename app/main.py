from fastapi import FastAPI
from dotenv import load_dotenv
from app.api.router import api_router

load_dotenv()

app = FastAPI(title="Chat2SQL")

app.include_router(api_router)
