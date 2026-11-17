from __future__ import annotations

import re
from dataclasses import dataclass

from .types import MemoryKey


@dataclass(frozen=True, slots=True)
class ExtractedMemory:
    key: MemoryKey
    value: str
    confidence: float


class PreferenceExtractor:
    """Extract only explicit, low-risk preferences suitable for long-term storage."""

    _name_patterns = (
        re.compile(r"(?:以后)?(?:请)?(?:叫我|称呼我为|称呼我)\s*([A-Za-z0-9_\-\u4e00-\u9fff]{1,12})"),
        re.compile(r"我叫\s*([A-Za-z0-9_\-\u4e00-\u9fff]{1,12})"),
    )
    _station_patterns = (
        re.compile(r"我的常用(?:网点|站点)是\s*([^，。！？\n]{2,24})"),
        re.compile(r"我(?:经常|常)在\s*([^，。！？\n]{2,24}?(?:站|网点|口))\s*(?:借伞|还伞|使用)"),
        re.compile(r"我常去\s*([^，。！？\n]{2,24}?(?:站|网点|口))"),
    )
    _sensitive_markers = (
        "身份证",
        "银行卡",
        "信用卡",
        "密码",
        "手机号",
        "手机号码",
        "电话号码",
        "家庭住址",
        "详细地址",
    )

    def extract(self, content: str) -> tuple[ExtractedMemory, ...]:
        compact = " ".join(content.strip().split())
        if not compact:
            return ()

        candidates: dict[MemoryKey, ExtractedMemory] = {}
        name = self._first_match(self._name_patterns, compact)
        if name and self._is_safe(name):
            candidates["preferred_name"] = ExtractedMemory("preferred_name", name, 0.98)

        station = self._first_match(self._station_patterns, compact)
        if station and self._is_safe(station):
            candidates["frequent_station"] = ExtractedMemory("frequent_station", station, 0.95)

        if any(marker in compact for marker in ("回复简短", "简短一点", "简洁一点")):
            candidates["response_style"] = ExtractedMemory("response_style", "简洁", 0.99)
        elif any(marker in compact for marker in ("回复详细", "详细一点", "说详细些")):
            candidates["response_style"] = ExtractedMemory("response_style", "详细", 0.99)

        if any(marker in compact for marker in ("用英文回复", "英文回答", "说英文")):
            candidates["preferred_language"] = ExtractedMemory("preferred_language", "英文", 0.99)
        elif any(marker in compact for marker in ("用中文回复", "中文回答", "说中文")):
            candidates["preferred_language"] = ExtractedMemory("preferred_language", "中文", 0.99)

        return tuple(candidates.values())

    @classmethod
    def _first_match(cls, patterns: tuple[re.Pattern[str], ...], content: str) -> str | None:
        for pattern in patterns:
            match = pattern.search(content)
            if match:
                return match.group(1).strip(" ：:,，。.!！?？")
        return None

    @classmethod
    def _is_safe(cls, value: str) -> bool:
        if not value or len(value) > 24:
            return False
        if any(marker in value for marker in cls._sensitive_markers):
            return False
        if "@" in value or re.search(r"\d{6,}", value):
            return False
        return True
