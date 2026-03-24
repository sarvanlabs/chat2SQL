from pydantic import BaseModel

class QueryRequest(BaseModel):
    """Base Model for User Query"""
    query: str