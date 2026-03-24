from pydantic import BaseModel

class TextPromptRequest(BaseModel):
    """Base Model for User Query"""
    request: str