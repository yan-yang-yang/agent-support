from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Literal


Scenario = Literal["return", "billing", "nearby"]


@dataclass(frozen=True, slots=True)
class StreamScript:
    scenario: Scenario
    progress_labels: tuple[str, str, str]
    response: str
    card: dict[str, Any]


SCRIPTS: dict[Scenario, StreamScript] = {
    "return": StreamScript(
        scenario="return",
        progress_labels=("识别还伞问题", "查询租借记录", "整理处理建议"),
        response="我查到了你当前有一笔进行中的订单，系统暂时还没有收到有效的还伞确认。请先确认雨伞已推到底并听到提示音；如果当前伞桩已满，可以前往下方有空位的附近网点。",
        card={
            "kind": "rental",
            "startedAt": "今日 08:30",
            "station": "地铁 1 号线科技园站 A 口",
            "fee": "¥3.00",
            "status": "计费中",
        },
    ),
    "billing": StreamScript(
        scenario="billing",
        progress_labels=("识别计费问题", "核对订单明细", "整理费用说明"),
        response="我已经核对了最近一笔订单。当前总费用由基础使用费和超时费组成，金额与业务记录一致。如果你仍有异议，我可以继续为这笔订单创建待处理工单。",
        card={
            "kind": "billing",
            "orderId": "US202611160083",
            "duration": "42 分钟",
            "baseFee": "¥2.00",
            "overtimeFee": "¥1.00",
            "total": "¥3.00",
        },
    ),
    "nearby": StreamScript(
        scenario="nearby",
        progress_labels=("识别网点需求", "查询附近网点", "筛选可用位置"),
        response="我找到了 2 个可以正常还伞的附近网点，库存和空位可能会实时变化，建议优先前往距离最近的科技园站 B 口。",
        card={
            "kind": "stations",
            "stations": [
                {"name": "科技园站 B 口", "distance": "180m", "umbrellas": 6, "docks": 4},
                {"name": "文三路园区南门", "distance": "420m", "umbrellas": 3, "docks": 7},
            ],
        },
    ),
}


def detect_scenario(text: str) -> Scenario:
    if any(keyword in text for keyword in ("附近", "网点", "哪里", "位置", "借伞")):
        return "nearby"
    if any(keyword in text for keyword in ("还伞", "插回", "伞桩", "还不了", "归还")):
        return "return"
    if any(keyword in text for keyword in ("费用", "扣费", "计费", "退款", "金额")):
        return "billing"
    return "return"


def script_for(text: str) -> StreamScript:
    return SCRIPTS[detect_scenario(text)]


def progress_steps(labels: tuple[str, str, str], active_index: int) -> list[dict[str, str]]:
    return [
        {
            "label": label,
            "state": "complete" if index < active_index else "active" if index == active_index else "pending",
        }
        for index, label in enumerate(labels)
    ]
