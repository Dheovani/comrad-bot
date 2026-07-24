"""Provider-neutral AI request models."""

from typing import Literal

from pydantic import BaseModel, Field


class AIMessage(BaseModel):
    role: Literal["user", "assistant"]
    content: str = Field(min_length=1, max_length=20000)


class SummaryMessage(BaseModel):
    """A bounded piece of Discord conversation supplied for one summary request."""

    author: str = Field(min_length=1, max_length=100)
    content: str = Field(min_length=1, max_length=4000)
