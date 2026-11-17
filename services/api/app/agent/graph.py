from __future__ import annotations

from typing import Literal

from langgraph.graph import END, START, StateGraph

from ..tools.executor import ToolExecutor
from ..tools.types import ToolContext
from .composer import compose_result
from .planner import next_tool
from .router import route_scenario
from .state import AgentState


def build_support_graph(executor: ToolExecutor):
    async def classify(state: AgentState) -> dict[str, object]:
        scenario = route_scenario(
            state["user_message"],
            tuple(state.get("prior_user_messages", [])),
        )
        return {
            "scenario": scenario,
            "stage": "fallback" if scenario == "unknown" else "planning",
            "error_code": "UNSUPPORTED_INTENT" if scenario == "unknown" else None,
        }

    def after_classify(state: AgentState) -> Literal["plan_tool", "safe_fallback"]:
        return "safe_fallback" if state["scenario"] == "unknown" else "plan_tool"

    async def plan_tool(state: AgentState) -> dict[str, object]:
        last_result = state.get("tool_results", [])[-1] if state.get("tool_results") else None
        if last_result and last_result["status"] != "success":
            return {
                "planned_tool": None,
                "stage": "fallback",
                "error_code": last_result.get("error_code") or "TOOL_FAILED",
            }

        planned = next_tool(state)
        if planned is None:
            return {"planned_tool": None, "stage": "composing"}
        if state.get("tool_call_count", 0) >= state["max_tool_calls"]:
            return {
                "planned_tool": None,
                "stage": "fallback",
                "error_code": "TOOL_LOOP_LIMIT",
            }
        return {"planned_tool": planned, "stage": "executing"}

    def after_plan(state: AgentState) -> Literal["execute_tool", "compose", "safe_fallback"]:
        if state["stage"] == "fallback":
            return "safe_fallback"
        if state["planned_tool"] is None:
            return "compose"
        return "execute_tool"

    async def execute_tool(state: AgentState) -> dict[str, object]:
        planned = state["planned_tool"]
        assert planned is not None
        result = await executor.execute(
            planned["name"],
            planned["arguments"],
            ToolContext(
                user_id=state["user_id"],
                conversation_id=state["conversation_id"],
                request_id=state["request_id"],
                tool_call_index=state["tool_call_count"],
                max_tool_calls=state["max_tool_calls"],
            ),
        )
        return {
            "planned_tool": None,
            "tool_results": [*state.get("tool_results", []), result.to_state()],
            "executed_tools": [*state.get("executed_tools", []), planned["name"]],
            "tool_call_count": state.get("tool_call_count", 0) + 1,
            "stage": "planning",
        }

    async def compose(state: AgentState) -> dict[str, object]:
        response, card = compose_result(state)
        return {
            "verified_response": response,
            "card": card,
            "safe_fallback": False,
            "stage": "completed",
        }

    async def safe_fallback(state: AgentState) -> dict[str, object]:
        error_code = state.get("error_code") or "SAFE_FALLBACK"
        if error_code == "UNSUPPORTED_INTENT":
            response = "我目前可以协助处理还伞失败、计费疑问和附近网点查询。请描述你遇到的具体情况。"
        elif error_code == "TOOL_LOOP_LIMIT":
            response = "本次自动排查达到安全上限，我没有继续调用业务工具，也没有修改订单或账单。请稍后重试。"
        else:
            response = "业务信息暂时查询失败，我没有执行订单、计费或退款修改。请稍后重试。"
        return {
            "verified_response": response,
            "card": None,
            "safe_fallback": True,
            "stage": "completed",
        }

    graph = StateGraph(AgentState)
    graph.add_node("classify", classify)
    graph.add_node("plan_tool", plan_tool)
    graph.add_node("execute_tool", execute_tool)
    graph.add_node("compose", compose)
    graph.add_node("safe_fallback", safe_fallback)
    graph.add_edge(START, "classify")
    graph.add_conditional_edges(
        "classify",
        after_classify,
        {"plan_tool": "plan_tool", "safe_fallback": "safe_fallback"},
    )
    graph.add_conditional_edges(
        "plan_tool",
        after_plan,
        {
            "execute_tool": "execute_tool",
            "compose": "compose",
            "safe_fallback": "safe_fallback",
        },
    )
    graph.add_edge("execute_tool", "plan_tool")
    graph.add_edge("compose", END)
    graph.add_edge("safe_fallback", END)
    return graph.compile()
