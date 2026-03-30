from pydantic import BaseModel


class TextQueryRequest(BaseModel):
    """Base Model for User Query"""

    query: str
