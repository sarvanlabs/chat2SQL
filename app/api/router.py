from fastapi import APIRouter

from app.api.routes.textquery import router as textquery_router
from app.api.routes.root import root_router

api_router = APIRouter()

api_router.include_router(root_router)
api_router.include_router(
    textquery_router, prefix="/v1/query/text", tags=["v1/query/text"]
)
