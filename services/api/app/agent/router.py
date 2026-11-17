from __future__ import annotations

from .state import Scenario


PROGRESS_LABELS: dict[Scenario, tuple[str, str, str]] = {
    "return_failure": ("识别还伞问题", "调用租借与网点工具", "整理处理建议"),
    "billing_dispute": ("识别计费问题", "调用订单与计费工具", "整理费用说明"),
    "nearby_station": ("识别网点需求", "调用附近网点工具", "筛选可用位置"),
    "unknown": ("识别用户问题", "检查可处理范围", "提供下一步建议"),
}


def route_scenario(text: str) -> Scenario:
    compact = "".join(text.lower().split())
    return_markers = (
        "还不了",
        "无法还",
        "不能还",
        "还伞失败",
        "插不进去",
        "插回",
        "伞桩",
        "归还失败",
        "还伞后",
    )
    billing_markers = ("费用", "扣费", "扣了", "计费", "金额", "退款", "多扣", "账单")
    nearby_markers = ("附近", "网点", "哪里能借", "哪里可以借", "哪里能还", "位置")

    if any(marker in compact for marker in return_markers):
        return "return_failure"
    if any(marker in compact for marker in billing_markers):
        return "billing_dispute"
    if any(marker in compact for marker in nearby_markers) or "借伞" in compact:
        return "nearby_station"
    return "unknown"


def progress_labels(text: str) -> tuple[str, str, str]:
    return PROGRESS_LABELS[route_scenario(text)]
