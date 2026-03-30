from fastapi import APIRouter
from app.schemas.textqueryrequest import TextQueryRequest
from app.core.handlers.query_handler import QueryHandler
import asyncio
import time

router = APIRouter()


@router.post("/")
async def query(textprompt: TextQueryRequest):
    """"""
    queryhandler = QueryHandler()
    return await queryhandler.process(textprompt)
