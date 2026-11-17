from __future__ import annotations

from datetime import datetime
from typing import Any

from .state import AgentState


def compose_result(state: AgentState) -> tuple[str, dict[str, Any] | None]:
    if state["scenario"] == "return_failure":
        return _compose_return(state)
    if state["scenario"] == "billing_dispute":
        return _compose_billing(state)
    if state["scenario"] == "nearby_station":
        return _compose_nearby(state)
    if state["scenario"] == "profile_update":
        return (
            "好的，我已保存你明确提供的称呼或客服偏好，后续会话会继续使用。"
            "订单、金额和租借状态不会作为长期记忆保存，仍会实时查询业务系统。",
            None,
        )
    return "我暂时无法判断你遇到的问题，请描述还伞、计费或查找附近网点中的具体情况。", None


def _compose_return(state: AgentState) -> tuple[str, dict[str, Any] | None]:
    active = _data(state, "get_active_rental")
    ticket = _data(state, "create_support_ticket")
    if active is None:
        orders = _data(state, "list_recent_orders") or []
        suffix = f"我找到了 {len(orders)} 笔最近订单，请补充大致借伞时间。" if orders else "当前也没有最近订单可供核对。"
        return f"我查询了当前用户，暂时没有发现进行中的租借。{suffix}", None

    station = _data(state, "get_station_status") or {}
    billing = _data(state, "get_order_billing") or {"total_amount": 0}
    nearby = _data(state, "find_nearby_stations") or []
    if not station.get("online", False):
        diagnosis = "当前网点设备处于离线状态"
    elif int(station.get("available_docks", 0)) == 0:
        diagnosis = "当前网点在线，但可还空位为 0"
    else:
        diagnosis = f"当前网点还有 {station.get('available_docks', 0)} 个可还空位"
    suggestion = (
        f"建议前往 {nearby[0]['name']}，该网点当前有 {nearby[0]['available_docks']} 个空位。"
        if nearby
        else "请重新插紧雨伞并等待提示音。"
    )
    ticket_text = f" 已创建工单 {ticket['id']}，状态为待处理。" if ticket else ""
    response = f"我查到了你当前有一笔进行中的订单。{diagnosis}。{suggestion}{ticket_text}"
    return response, {
        "kind": "rental",
        "startedAt": _display_time(active["started_at"]),
        "station": station.get("name", "未知网点"),
        "fee": _money(float(billing.get("total_amount", 0))),
        "status": "计费中",
    }


def _compose_billing(state: AgentState) -> tuple[str, dict[str, Any] | None]:
    orders = _data(state, "list_recent_orders") or []
    if not orders:
        return "我查询了当前用户，暂时没有找到可以核对的最近订单。请补充大致借伞时间。", None
    order = orders[0]
    billing = _data(state, "get_order_billing") or {"items": [], "total_amount": 0}
    amounts = {item["code"]: float(item["amount"]) for item in billing["items"]}
    ticket = _data(state, "create_support_ticket")
    ticket_text = f" 已创建工单 {ticket['id']}，业务人员会继续复核。" if ticket else ""
    response = (
        f"我已经通过计费工具核对订单 {order['id']}。业务记录显示合计 "
        f"{_money(float(billing['total_amount']))}，由下方计费项目组成。"
        f"系统没有执行退款或修改账单。{ticket_text}"
    )
    return response, {
        "kind": "billing",
        "orderId": order["id"],
        "duration": f"{order['duration_minutes']} 分钟",
        "baseFee": _money(amounts.get("base_fee", 0)),
        "overtimeFee": _money(amounts.get("overtime_fee", 0)),
        "total": _money(float(billing["total_amount"])),
    }


def _compose_nearby(state: AgentState) -> tuple[str, dict[str, Any] | None]:
    stations = _data(state, "find_nearby_stations") or []
    if not stations:
        return "当前位置附近暂时没有查询到可用网点，库存会实时变化，建议稍后重试。", None
    visible = stations[:3]
    purpose = "借伞" if any(word in state["user_message"] for word in ("借伞", "借一把")) else "还伞"
    response = (
        f"我通过网点工具找到了 {len(visible)} 个可以正常{purpose}的附近网点。"
        f"建议优先前往 {visible[0]['name']}；库存数据来自业务服务，可能实时变化。"
    )
    return response, {
        "kind": "stations",
        "stations": [
            {
                "name": station["name"],
                "distance": _distance(int(station.get("distance_m") or 0)),
                "umbrellas": station["available_umbrellas"],
                "docks": station["available_docks"],
            }
            for station in visible
        ],
    }


def _data(state: AgentState, name: str) -> Any:
    result = next(
        (item for item in reversed(state.get("tool_results", [])) if item["name"] == name),
        None,
    )
    return result.get("data") if result and result.get("status") == "success" else None


def _money(amount: float) -> str:
    return f"¥{amount:.2f}"


def _display_time(value: str) -> str:
    return datetime.fromisoformat(value).strftime("%m月%d日 %H:%M")


def _distance(distance_m: int) -> str:
    return f"{distance_m}m" if distance_m < 1000 else f"{distance_m / 1000:.1f}km"
