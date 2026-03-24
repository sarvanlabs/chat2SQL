from fastapi import APIRouter
from backendapp.schemas.queryrequest import QueryRequest
import asyncio
import time

router = APIRouter()

@router.post("/")
async def query(query: QueryRequest):
    return {"data": query.query}
