from __future__ import annotations

from datetime import datetime
from typing import Any, Literal

from pydantic import BaseModel, Field


class ConversationDTO(BaseModel):
    id: str
    title: str
    preview: str
    created_at: datetime
    updated_at: datetime
    message_count: int


class MessageDTO(BaseModel):
    id: str
    conversation_id: str
    role: Literal["user", "assistant"]
    content: str
    created_at: datetime
    card: dict[str, Any] | None = None


class CreateConversationRequest(BaseModel):
    title: str | None = Field(default=None, max_length=80)


class SendMessageRequest(BaseModel):
    content: str = Field(min_length=1, max_length=500)
    request_id: str = Field(min_length=8, max_length=80)


class ProgressStep(BaseModel):
    label: str
    state: Literal["pending", "active", "complete"]
