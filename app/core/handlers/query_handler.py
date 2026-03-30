from fastapi import APIRouter
from app.core.handlers.base_handler import BaseHandler
from app.core.company_chat_service import CompanyChatService


class QueryHandler(BaseHandler):
    """A handler class to orchestrate the processing of text prompts for API routes.
    Allows for pre-processing and post-processing around the actual route handler logic.
    """

    def __init__(self):
        super().__init__()

    def validate(self, query):  # type: ignore
        """A method to perform any necessary validation on the incoming query before processing."""
        if query.query.strip() == "":
            raise ValueError("Query cannot be empty")

    async def process(self, query, *args, **kwargs):  # type: ignore
        """This method is used to handle the route to orchestrator and perform any validation or pre-processing before the actual route handler logic is executed."""
        print("Pre-processing before route handler")
        try:
            self.validate(query)
            service = CompanyChatService()
            response_text = await service.handle(query.query)
            return response_text
        except Exception as e:
            print(f"Error in handling route: {e}")
            return {"error": str(e)}
