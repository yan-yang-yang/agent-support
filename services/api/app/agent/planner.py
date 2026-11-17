from __future__ import annotations

from typing import Any

from .state import AgentState, PlannedTool


def next_tool(state: AgentState) -> PlannedTool | None:
    scenario = state["scenario"]
    if scenario == "return_failure":
        return _return_failure_tool(state)
    if scenario == "billing_dispute":
        return _billing_tool(state)
    if scenario == "nearby_station":
        return _nearby_tool(state)
    return None


def _return_failure_tool(state: AgentState) -> PlannedTool | None:
    active = _result(state, "get_active_rental")
    if active is None:
        return {"name": "get_active_rental", "arguments": {}}
    rental = active.get("data")
    if rental is None:
        if _result(state, "list_recent_orders") is None:
            return {"name": "list_recent_orders", "arguments": {"limit": 5}}
        return None

    station = _result(state, "get_station_status")
    if station is None:
        return {
            "name": "get_station_status",
            "arguments": {"station_id": str(rental["station_id"])},
        }
    billing = _result(state, "get_order_billing")
    if billing is None:
        return {
            "name": "get_order_billing",
            "arguments": {"order_id": str(rental["order_id"])},
        }
    nearby = _result(state, "find_nearby_stations")
    if nearby is None:
        station_data = station["data"]
        return {
            "name": "find_nearby_stations",
            "arguments": {
                "lat": station_data["lat"],
                "lng": station_data["lng"],
                "purpose": "return",
                "radius_m": 3000,
            },
        }
    if _needs_ticket(state["user_message"], "return_failure") and _result(
        state, "create_support_ticket"
    ) is None:
        station_data = station["data"]
        return {
            "name": "create_support_ticket",
            "arguments": {
                "category": "return_failure",
                "references": {
                    "rental_id": rental["id"],
                    "order_id": rental["order_id"],
                    "station_id": station_data["id"],
                },
                "summary": "用户完成安全排查后仍无法归还雨伞",
                "idempotency_key": f"{state['request_id']}:return_failure",
            },
        }
    return None


def _billing_tool(state: AgentState) -> PlannedTool | None:
    orders = _result(state, "list_recent_orders")
    if orders is None:
        return {"name": "list_recent_orders", "arguments": {"limit": 5}}
    order_list = orders.get("data") or []
    if not order_list:
        return None
    billing = _result(state, "get_order_billing")
    if billing is None:
        return {
            "name": "get_order_billing",
            "arguments": {"order_id": str(order_list[0]["id"])},
        }
    if _needs_ticket(state["user_message"], "billing_dispute") and _result(
        state, "create_support_ticket"
    ) is None:
        return {
            "name": "create_support_ticket",
            "arguments": {
                "category": "billing_dispute",
                "references": {
                    "rental_id": None,
                    "order_id": order_list[0]["id"],
                    "station_id": None,
                },
                "summary": "用户对业务系统计费明细仍有异议，需要人工复核",
                "idempotency_key": f"{state['request_id']}:billing_dispute",
            },
        }
    return None


def _nearby_tool(state: AgentState) -> PlannedTool | None:
    if _result(state, "find_nearby_stations") is not None:
        return None
    purpose = "borrow" if any(word in state["user_message"] for word in ("借伞", "借一把")) else "return"
    return {
        "name": "find_nearby_stations",
        "arguments": {
            "lat": 30.2741,
            "lng": 120.1551,
            "purpose": purpose,
            "radius_m": 3000,
        },
    }


def _needs_ticket(text: str, scenario: str) -> bool:
    common = ("工单", "人工", "投诉", "还是不行", "解决不了")
    if any(marker in text for marker in common):
        return True
    return scenario == "billing_dispute" and "退款" in text


def _result(state: AgentState, name: str) -> dict[str, Any] | None:
    return next(
        (result for result in reversed(state.get("tool_results", [])) if result["name"] == name),
        None,
    )
