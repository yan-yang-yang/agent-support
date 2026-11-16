from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from typing import Any, Literal

from .business import BusinessGateway


Scenario = Literal["return", "billing", "nearby"]


@dataclass(frozen=True, slots=True)
class StreamScript:
    scenario: Scenario
    progress_labels: tuple[str, str, str]
    response: str
    card: dict[str, Any] | None


PROGRESS_LABELS: dict[Scenario, tuple[str, str, str]] = {
    "return": ("识别还伞问题", "查询租借与网点", "整理处理建议"),
    "billing": ("识别计费问题", "核对订单明细", "整理费用说明"),
    "nearby": ("识别网点需求", "查询附近网点", "筛选可用位置"),
}


def detect_scenario(text: str) -> Scenario:
    if any(keyword in text for keyword in ("附近", "网点", "哪里", "位置", "借伞")):
        return "nearby"
    if any(keyword in text for keyword in ("还伞", "插回", "伞桩", "还不了", "归还")):
        return "return"
    if any(keyword in text for keyword in ("费用", "扣费", "计费", "退款", "金额")):
        return "billing"
    return "return"


async def script_for(text: str, user_id: str, gateway: BusinessGateway) -> StreamScript:
    scenario = detect_scenario(text)
    if scenario == "return":
        return await _return_script(user_id, gateway)
    if scenario == "billing":
        return await _billing_script(user_id, gateway)
    return await _nearby_script(gateway)


async def _return_script(user_id: str, gateway: BusinessGateway) -> StreamScript:
    rental = await gateway.get_active_rental(user_id)
    if rental is None:
        return StreamScript(
            scenario="return",
            progress_labels=PROGRESS_LABELS["return"],
            response="我查询了当前用户，暂时没有发现进行中的租借订单。你可以描述大致借伞时间，我会继续从最近订单中排查。",
            card=None,
        )

    station = await gateway.get_station_status(str(rental["station_id"]))
    billing = await gateway.get_order_billing(str(rental["order_id"]))
    alternatives = await gateway.find_nearby_stations(
        lat=float(station["lat"]),
        lng=float(station["lng"]),
        purpose="return",
    )
    nearest = alternatives[0] if alternatives else None

    if not station["online"]:
        diagnosis = "当前网点设备处于离线状态"
    elif int(station["available_docks"]) == 0:
        diagnosis = "当前网点在线，但可还空位为 0"
    else:
        diagnosis = f"当前网点还有 {station['available_docks']} 个可还空位"

    next_step = (
        f"如果仍无法归还，建议前往 {nearest['name']}，该网点当前有 {nearest['available_docks']} 个空位。"
        if nearest
        else "请重新插紧雨伞并等待提示音；如果仍失败，可以继续创建待处理工单。"
    )
    return StreamScript(
        scenario="return",
        progress_labels=PROGRESS_LABELS["return"],
        response=f"我查到了你当前有一笔进行中的订单。{diagnosis}。{next_step}",
        card={
            "kind": "rental",
            "startedAt": _display_time(str(rental["started_at"])),
            "station": str(station["name"]),
            "fee": _money(float(billing["total_amount"])),
            "status": "计费中",
        },
    )


async def _billing_script(user_id: str, gateway: BusinessGateway) -> StreamScript:
    orders = await gateway.list_recent_orders(user_id, limit=5)
    if not orders:
        return StreamScript(
            scenario="billing",
            progress_labels=PROGRESS_LABELS["billing"],
            response="我查询了当前用户，暂时没有找到可以核对的最近订单。请提供大致借伞时间，我会继续协助定位。",
            card=None,
        )

    order = orders[0]
    billing = await gateway.get_order_billing(str(order["id"]))
    amounts = {str(item["code"]): float(item["amount"]) for item in billing["items"]}
    return StreamScript(
        scenario="billing",
        progress_labels=PROGRESS_LABELS["billing"],
        response=(
            f"我已经核对订单 {order['id']}。业务记录显示合计 {_money(float(billing['total_amount']))}，"
            "由下方计费项目组成。如果你仍有异议，可以继续为这笔订单创建待处理工单。"
        ),
        card={
            "kind": "billing",
            "orderId": str(order["id"]),
            "duration": f"{order['duration_minutes']} 分钟",
            "baseFee": _money(amounts.get("base_fee", 0)),
            "overtimeFee": _money(amounts.get("overtime_fee", 0)),
            "total": _money(float(billing["total_amount"])),
        },
    )


async def _nearby_script(gateway: BusinessGateway) -> StreamScript:
    stations = await gateway.find_nearby_stations(
        lat=30.2741,
        lng=120.1551,
        purpose="return",
    )
    visible_stations = stations[:3]
    if not visible_stations:
        return StreamScript(
            scenario="nearby",
            progress_labels=PROGRESS_LABELS["nearby"],
            response="当前位置附近暂时没有查询到可用的还伞网点。库存会实时变化，建议稍后重试。",
            card=None,
        )

    return StreamScript(
        scenario="nearby",
        progress_labels=PROGRESS_LABELS["nearby"],
        response=(
            f"我找到了 {len(visible_stations)} 个可以正常还伞的附近网点。"
            f"建议优先前往距离最近的 {visible_stations[0]['name']}，库存和空位可能实时变化。"
        ),
        card={
            "kind": "stations",
            "stations": [
                {
                    "name": station["name"],
                    "distance": _distance(int(station["distance_m"])),
                    "umbrellas": station["available_umbrellas"],
                    "docks": station["available_docks"],
                }
                for station in visible_stations
            ],
        },
    )


def progress_labels_for(text: str) -> tuple[str, str, str]:
    return PROGRESS_LABELS[detect_scenario(text)]


def _money(amount: float) -> str:
    return f"¥{amount:.2f}"


def _display_time(value: str) -> str:
    parsed = datetime.fromisoformat(value)
    return parsed.strftime("%m月%d日 %H:%M")


def _distance(distance_m: int) -> str:
    if distance_m < 1000:
        return f"{distance_m}m"
    return f"{distance_m / 1000:.1f}km"


def progress_steps(labels: tuple[str, str, str], active_index: int) -> list[dict[str, str]]:
    return [
        {
            "label": label,
            "state": "complete" if index < active_index else "active" if index == active_index else "pending",
        }
        for index, label in enumerate(labels)
    ]
