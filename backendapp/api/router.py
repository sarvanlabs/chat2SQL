from fastapi import APIRouter

from backendapp.api.routes.textprompt import router as textprompt_router
from backendapp.api.routes.root import root_router

api_router = APIRouter()

api_router.include_router(root_router)
api_router.include_router(textprompt_router, prefix="/v1/textprompt", tags=["v1/textprompt"])