from fastapi import FastAPI
from backendapp.api.router import api_router

app = FastAPI(title='Chat2SQL')

app.include_router(api_router)

