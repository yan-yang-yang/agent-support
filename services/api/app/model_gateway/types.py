from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Literal, TypeAlias

from pydantic import BaseModel, Field


VERIFIED_RESPONSE_MARKER = "<<VERIFIED_RESPONSE>>"


class FunctionCall(BaseModel):
    name: str
    arguments: str


class AssistantToolCall(BaseModel):
    id: str
    type: Literal["function"] = "function"
    function: FunctionCall


class ModelMessage(BaseModel):
    role: Literal["system", "user", "assistant", "tool"]
    content: str | None = None
    name: str | None = None
    tool_call_id: str | None = None
    tool_calls: list[AssistantToolCall] | None = None


class ToolDefinition(BaseModel):
    name: str = Field(min_length=1, max_length=64)
    description: str = Field(min_length=1, max_length=500)
    parameters: dict[str, Any]
    strict: bool = True


class ModelRequest(BaseModel):
    messages: list[ModelMessage]
    tools: list[ToolDefinition] = Field(default_factory=list)
    temperature: float | None = Field(default=None, ge=0, le=2)
    max_output_tokens: int | None = Field(default=None, ge=1, le=32_768)
    request_id: str | None = None
    conversation_id: str | None = None


@dataclass(frozen=True, slots=True)
class TextDelta:
    delta: str
    kind: Literal["text_delta"] = field(default="text_delta", init=False)


@dataclass(frozen=True, slots=True)
class ToolCallDelta:
    index: int
    call_id: str | None
    name: str | None
    arguments_delta: str
    kind: Literal["tool_call_delta"] = field(default="tool_call_delta", init=False)


@dataclass(frozen=True, slots=True)
class Usage:
    prompt_tokens: int
    completion_tokens: int
    total_tokens: int
    kind: Literal["usage"] = field(default="usage", init=False)


@dataclass(frozen=True, slots=True)
class Completed:
    finish_reason: str
    kind: Literal["completed"] = field(default="completed", init=False)


ModelEvent: TypeAlias = TextDelta | ToolCallDelta | Usage | Completed
