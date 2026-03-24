from fastapi import APIRouter
from backendapp.schemas.textpromptrequest import TextPromptRequest
import asyncio
import time

router = APIRouter()

@router.post("/")
async def query(textprompt: TextPromptRequest):
    return {"data": textprompt.request}
