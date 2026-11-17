from __future__ import annotations

from dataclasses import dataclass

from .repository import TraceRepository
from .types import TraceStatus, TurnTrace


@dataclass(slots=True)
class TraceSession:
    repository: TraceRepository
    trace: TurnTrace
    scenario: str | None = None
    safe_fallback: bool = False
    error_code: str | None = None
    recent_message_count: int = 0
    summary_used: bool = False
    long_term_memory_count: int = 0
    finished: bool = False

    @property
    def id(self) -> str:
        return self.trace.id

    async def finish(self, status: TraceStatus, error_code: str | None = None) -> None:
        if self.finished:
            return
        self.finished = True
        await self.repository.complete(
            self.trace.id,
            status=status,
            scenario=self.scenario,
            safe_fallback=self.safe_fallback,
            error_code=error_code or self.error_code,
            recent_message_count=self.recent_message_count,
            summary_used=self.summary_used,
            long_term_memory_count=self.long_term_memory_count,
        )


class TraceService:
    def __init__(self, repository: TraceRepository) -> None:
        self.repository = repository

    async def start_turn(
        self,
        *,
        request_id: str,
        conversation_id: str,
        user_id: str,
        content: str,
    ) -> TraceSession:
        trace = await self.repository.start(
            request_id=request_id,
            conversation_id=conversation_id,
            user_id=user_id,
            input_chars=len(content),
        )
        return TraceSession(repository=self.repository, trace=trace)
