from fastapi import APIRouter

from backendapp.api.routes.query import router as query_router
from backendapp.api.routes.root import root_router

api_router = APIRouter()

api_router.include_router(root_router)
api_router.include_router(query_router, prefix="/v1/query", tags=["v1/query"])