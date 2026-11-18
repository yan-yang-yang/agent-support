from __future__ import annotations

from datetime import datetime
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field


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


class AuthUserDTO(BaseModel):
    user_id: str
    display_name: str
    source: str


class ExchangeLaunchTokenRequest(BaseModel):
    launch_token: str = Field(min_length=32, max_length=4096)


class DemoSessionRequest(BaseModel):
    client_id: str = Field(min_length=8, max_length=80, pattern=r"^[A-Za-z0-9_-]+$")
    profile: Literal[
        "demo-user",
        "demo-return-user",
        "demo-billing-user",
        "demo-nearby-user",
    ] = "demo-user"


class ProgressStep(BaseModel):
    label: str
    state: Literal["pending", "active", "complete"]


class UserMemoryDTO(BaseModel):
    key: Literal[
        "preferred_name",
        "frequent_station",
        "response_style",
        "preferred_language",
    ]
    label: str
    value: str
    updated_at: datetime


class DeleteMemoriesResponse(BaseModel):
    deleted: int


class TurnTraceDTO(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    request_id: str
    conversation_id: str
    scenario: str | None
    status: Literal["started", "completed", "failed", "cancelled"]
    safe_fallback: bool
    error_code: str | None
    input_chars: int
    recent_message_count: int
    summary_used: bool
    long_term_memory_count: int
    tool_call_count: int
    tool_success_count: int
    model_call_count: int
    model_failure_count: int
    prompt_tokens: int
    completion_tokens: int
    total_tokens: int
    duration_ms: int | None
    created_at: datetime
    completed_at: datetime | None


class ToolSpanDTO(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    name: str
    status: str
    error_code: str | None
    retryable: bool
    latency_ms: int | None
    created_at: datetime
    completed_at: datetime | None


class ModelSpanDTO(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    provider: str
    model: str
    status: str
    error_code: str | None
    prompt_tokens: int
    completion_tokens: int
    total_tokens: int
    latency_ms: int | None
    created_at: datetime
    completed_at: datetime | None


class TraceDetailDTO(BaseModel):
    trace: TurnTraceDTO
    tool_spans: list[ToolSpanDTO]
    model_spans: list[ModelSpanDTO]


class TraceSummaryDTO(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    total_turns: int
    completed_turns: int
    failed_turns: int
    cancelled_turns: int
    safe_fallback_turns: int
    average_duration_ms: float
    tool_calls: int
    tool_success_rate: float
    model_calls: int
    model_failure_rate: float
    total_tokens: int
