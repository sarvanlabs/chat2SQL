from pydantic import BaseModel


class TextPromptResponse(BaseModel):
    """Base Model for User Query"""

    response: str
