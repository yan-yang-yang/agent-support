from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from typing import Literal

from ..schemas import MessageDTO


MemoryKey = Literal[
    "preferred_name",
    "frequent_station",
    "response_style",
    "preferred_language",
]


MEMORY_LABELS: dict[MemoryKey, str] = {
    "preferred_name": "用户称呼",
    "frequent_station": "常用网点",
    "response_style": "回复风格",
    "preferred_language": "回复语言",
}


@dataclass(frozen=True, slots=True)
class UserMemory:
    user_id: str
    key: MemoryKey
    value: str
    source_conversation_id: str
    source_message_id: str
    confidence: float
    created_at: datetime
    updated_at: datetime


@dataclass(frozen=True, slots=True)
class ConversationMemory:
    conversation_id: str
    user_id: str
    summary: str
    summarized_message_count: int
    summarized_through_message_id: str | None
    revision: int
    created_at: datetime
    updated_at: datetime


@dataclass(frozen=True, slots=True)
class MemoryContext:
    summary: str | None
    recent_messages: tuple[MessageDTO, ...]
    long_term_memories: tuple[UserMemory, ...]

    def value(self, key: MemoryKey) -> str | None:
        memory = next((item for item in self.long_term_memories if item.key == key), None)
        return memory.value if memory else None
