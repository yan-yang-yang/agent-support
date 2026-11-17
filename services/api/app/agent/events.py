from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Literal, TypeAlias

from .state import Scenario


@dataclass(frozen=True, slots=True)
class ToolStartedEvent:
    name: str
    arguments: dict[str, object]
    kind: Literal["tool.started"] = "tool.started"


@dataclass(frozen=True, slots=True)
class ToolCompletedEvent:
    name: str
    status: str
    call_id: str
    error_code: str | None
    kind: Literal["tool.completed"] = "tool.completed"


@dataclass(frozen=True, slots=True)
class AgentResult:
    scenario: Scenario
    verified_response: str
    card: dict[str, Any] | None
    executed_tools: tuple[str, ...]
    tool_results: tuple[dict[str, Any], ...]
    safe_fallback: bool
    error_code: str | None


@dataclass(frozen=True, slots=True)
class AgentCompletedEvent:
    result: AgentResult
    kind: Literal["agent.completed"] = "agent.completed"


AgentEvent: TypeAlias = ToolStartedEvent | ToolCompletedEvent | AgentCompletedEvent
