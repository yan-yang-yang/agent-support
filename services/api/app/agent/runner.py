from __future__ import annotations

from collections.abc import AsyncIterator
from typing import Any

from ..tools.executor import ToolExecutor
from .events import AgentCompletedEvent, AgentEvent, AgentResult, ToolCompletedEvent, ToolStartedEvent
from .graph import build_support_graph
from .router import progress_labels
from .state import AgentState


class AgentRunner:
    def __init__(self, *, executor: ToolExecutor, max_tool_calls: int = 6) -> None:
        self.max_tool_calls = max_tool_calls
        self._graph = build_support_graph(executor)

    def progress_labels(self, text: str) -> tuple[str, str, str]:
        return progress_labels(text)

    async def stream_turn(
        self,
        *,
        user_id: str,
        conversation_id: str,
        request_id: str,
        content: str,
    ) -> AsyncIterator[AgentEvent]:
        current: AgentState = {
            "user_id": user_id,
            "conversation_id": conversation_id,
            "request_id": request_id,
            "user_message": content,
            "scenario": "unknown",
            "stage": "classifying",
            "planned_tool": None,
            "tool_results": [],
            "executed_tools": [],
            "tool_call_count": 0,
            "max_tool_calls": self.max_tool_calls,
            "verified_response": "",
            "card": None,
            "error_code": None,
            "safe_fallback": False,
        }
        config = {"recursion_limit": self.max_tool_calls * 2 + 10}
        async for update in self._graph.astream(current, config=config, stream_mode="updates"):
            for node_name, node_update in update.items():
                if not isinstance(node_update, dict):
                    continue
                current.update(node_update)
                if node_name == "plan_tool" and node_update.get("planned_tool"):
                    planned = node_update["planned_tool"]
                    yield ToolStartedEvent(
                        name=planned["name"],
                        arguments=planned["arguments"],
                    )
                if node_name == "execute_tool" and node_update.get("tool_results"):
                    result = node_update["tool_results"][-1]
                    yield ToolCompletedEvent(
                        name=result["name"],
                        status=result["status"],
                        call_id=result["call_id"],
                        error_code=result.get("error_code"),
                    )

        yield AgentCompletedEvent(
            AgentResult(
                scenario=current["scenario"],
                verified_response=current["verified_response"],
                card=current.get("card"),
                executed_tools=tuple(current.get("executed_tools", [])),
                tool_results=tuple(current.get("tool_results", [])),
                safe_fallback=current.get("safe_fallback", False),
                error_code=current.get("error_code"),
            )
        )

    async def run_turn(
        self,
        *,
        user_id: str,
        conversation_id: str,
        request_id: str,
        content: str,
    ) -> AgentResult:
        result: AgentResult | None = None
        async for event in self.stream_turn(
            user_id=user_id,
            conversation_id=conversation_id,
            request_id=request_id,
            content=content,
        ):
            if isinstance(event, AgentCompletedEvent):
                result = event.result
        if result is None:
            raise RuntimeError("Agent graph completed without a result")
        return result
