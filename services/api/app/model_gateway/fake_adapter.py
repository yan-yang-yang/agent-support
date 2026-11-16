from __future__ import annotations

import asyncio
from collections.abc import AsyncIterator, Callable
from typing import Any

from pydantic import BaseModel

from .protocol import StructuredT
from .repository import ModelCallRepository
from .types import (
    VERIFIED_RESPONSE_MARKER,
    Completed,
    ModelEvent,
    ModelRequest,
    TextDelta,
    Usage,
)


class FakeModelGateway:
    provider_name = "fake"
    model_name = "fake-support-v1"

    def __init__(
        self,
        *,
        repository: ModelCallRepository,
        character_delay: float = 0,
        response_resolver: Callable[[ModelRequest], str] | None = None,
        structured_payload: dict[str, Any] | None = None,
    ) -> None:
        self._repository = repository
        self._character_delay = character_delay
        self._response_resolver = response_resolver or self._default_response
        self._structured_payload = structured_payload

    async def close(self) -> None:
        return None

    async def stream_chat(self, request: ModelRequest) -> AsyncIterator[ModelEvent]:
        call = await self._repository.start(
            provider=self.provider_name,
            model=self.model_name,
            request_id=request.request_id,
            conversation_id=request.conversation_id,
        )
        usage: Usage | None = None
        finalized = False
        try:
            text = self._response_resolver(request)
            for character in text:
                if self._character_delay:
                    await asyncio.sleep(self._character_delay)
                yield TextDelta(character)

            usage = Usage(
                prompt_tokens=sum(len(message.content or "") for message in request.messages),
                completion_tokens=len(text),
                total_tokens=sum(len(message.content or "") for message in request.messages) + len(text),
            )
            yield usage
            await self._repository.complete(call.id, usage=usage, status="completed")
            finalized = True
            yield Completed("stop")
        except asyncio.CancelledError:
            await self._repository.complete(
                call.id,
                usage=usage,
                status="cancelled",
                error_code="CANCELLED",
            )
            finalized = True
            raise
        finally:
            if not finalized:
                await self._repository.complete(
                    call.id,
                    usage=usage,
                    status="cancelled",
                    error_code="STREAM_CLOSED",
                )

    async def complete_structured(
        self,
        request: ModelRequest,
        schema: type[StructuredT],
    ) -> StructuredT:
        call = await self._repository.start(
            provider=self.provider_name,
            model=self.model_name,
            request_id=request.request_id,
            conversation_id=request.conversation_id,
        )
        result = schema.model_validate(self._structured_payload or {})
        usage = Usage(prompt_tokens=0, completion_tokens=0, total_tokens=0)
        await self._repository.complete(call.id, usage=usage, status="completed")
        return result

    @staticmethod
    def _default_response(request: ModelRequest) -> str:
        content = next(
            (message.content for message in reversed(request.messages) if message.content),
            "",
        )
        if VERIFIED_RESPONSE_MARKER in content:
            return content.split(VERIFIED_RESPONSE_MARKER, 1)[1].strip()
        return content
