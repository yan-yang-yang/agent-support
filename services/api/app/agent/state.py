from __future__ import annotations

from typing import Any, Literal, TypedDict


Scenario = Literal["return_failure", "billing_dispute", "nearby_station", "unknown"]


class PlannedTool(TypedDict):
    name: str
    arguments: dict[str, object]


class AgentState(TypedDict, total=False):
    user_id: str
    conversation_id: str
    request_id: str
    user_message: str
    scenario: Scenario
    stage: Literal["classifying", "planning", "executing", "composing", "completed", "fallback"]
    planned_tool: PlannedTool | None
    tool_results: list[dict[str, Any]]
    executed_tools: list[str]
    tool_call_count: int
    max_tool_calls: int
    verified_response: str
    card: dict[str, Any] | None
    error_code: str | None
    safe_fallback: bool
