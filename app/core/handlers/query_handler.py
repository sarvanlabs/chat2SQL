from fastapi import APIRouter
from app.core.handlers.base_handler import BaseHandler
from app.core.orchestrator import Orchestrator


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
        """This method validates the query and delegates business flow to Orchestrator."""
        print("Pre-processing before route handler")
        try:
            self.validate(query)
            orchestrator = Orchestrator()
            response_text = await orchestrator.handle_query(query.query)
            return response_text
        except Exception as e:
            print(f"Error in handling route: {e}")
            return {"error": str(e)}
