from __future__ import annotations

from collections.abc import AsyncIterator
from typing import Protocol, TypeVar

from pydantic import BaseModel

from .types import ModelEvent, ModelRequest


StructuredT = TypeVar("StructuredT", bound=BaseModel)


class ModelGatewayError(RuntimeError):
    def __init__(
        self,
        message: str,
        *,
        safe_code: str,
        retryable: bool,
        status_code: int | None = None,
    ) -> None:
        super().__init__(message)
        self.safe_code = safe_code
        self.retryable = retryable
        self.status_code = status_code


class ModelGateway(Protocol):
    provider_name: str
    model_name: str

    def stream_chat(self, request: ModelRequest) -> AsyncIterator[ModelEvent]: ...

    async def complete_structured(
        self,
        request: ModelRequest,
        schema: type[StructuredT],
    ) -> StructuredT: ...

    async def close(self) -> None: ...
