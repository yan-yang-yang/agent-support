from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from typing import Literal


TraceStatus = Literal["started", "completed", "failed", "cancelled"]


@dataclass(frozen=True, slots=True)
class TurnTrace:
    id: str
    request_id: str
    conversation_id: str
    user_id: str
    scenario: str | None
    status: TraceStatus
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


@dataclass(frozen=True, slots=True)
class ToolSpan:
    id: str
    name: str
    status: str
    error_code: str | None
    retryable: bool
    latency_ms: int | None
    created_at: datetime
    completed_at: datetime | None


@dataclass(frozen=True, slots=True)
class ModelSpan:
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


@dataclass(frozen=True, slots=True)
class TraceDetail:
    trace: TurnTrace
    tool_spans: tuple[ToolSpan, ...]
    model_spans: tuple[ModelSpan, ...]


@dataclass(frozen=True, slots=True)
class TraceSummary:
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
