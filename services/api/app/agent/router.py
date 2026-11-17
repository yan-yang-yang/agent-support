from __future__ import annotations

from .state import Scenario


PROGRESS_LABELS: dict[Scenario, tuple[str, str, str]] = {
    "return_failure": ("识别还伞问题", "调用租借与网点工具", "整理处理建议"),
    "billing_dispute": ("识别计费问题", "调用订单与计费工具", "整理费用说明"),
    "nearby_station": ("识别网点需求", "调用附近网点工具", "筛选可用位置"),
    "profile_update": ("识别用户偏好", "安全保存偏好", "确认记忆结果"),
    "unknown": ("识别用户问题", "检查可处理范围", "提供下一步建议"),
}


def route_scenario(text: str, prior_user_messages: tuple[str, ...] = ()) -> Scenario:
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
    profile_markers = (
        "以后叫我",
        "称呼我",
        "我叫",
        "常用网点",
        "回复简短",
        "简短一点",
        "回复详细",
        "详细一点",
        "用中文回复",
        "用英文回复",
    )

    direct = _direct_scenario(
        compact,
        return_markers=return_markers,
        billing_markers=billing_markers,
        nearby_markers=nearby_markers,
        profile_markers=profile_markers,
    )
    if direct != "unknown":
        return direct

    follow_up_markers = ("还是不行", "那怎么办", "怎么处理", "然后呢", "接下来呢", "这个问题")
    if any(marker in compact for marker in follow_up_markers):
        for previous in reversed(prior_user_messages):
            previous_scenario = route_scenario(previous)
            if previous_scenario in {"return_failure", "billing_dispute", "nearby_station"}:
                return previous_scenario
    return "unknown"


def progress_labels(
    text: str,
    prior_user_messages: tuple[str, ...] = (),
) -> tuple[str, str, str]:
    return PROGRESS_LABELS[route_scenario(text, prior_user_messages)]


def _direct_scenario(
    compact: str,
    *,
    return_markers: tuple[str, ...],
    billing_markers: tuple[str, ...],
    nearby_markers: tuple[str, ...],
    profile_markers: tuple[str, ...],
) -> Scenario:
    if any(marker in compact for marker in profile_markers):
        return "profile_update"
    if any(marker in compact for marker in return_markers):
        return "return_failure"
    if any(marker in compact for marker in billing_markers):
        return "billing_dispute"
    if any(marker in compact for marker in nearby_markers) or "借伞" in compact:
        return "nearby_station"
    return "unknown"
