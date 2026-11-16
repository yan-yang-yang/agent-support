from __future__ import annotations

import asyncio
import sqlite3

from pydantic import BaseModel

from app.model_gateway.fake_adapter import FakeModelGateway
from app.model_gateway.repository import ModelCallRepository
from app.model_gateway.types import (
    VERIFIED_RESPONSE_MARKER,
    Completed,
    ModelMessage,
    ModelRequest,
    TextDelta,
    Usage,
)


class Classification(BaseModel):
    scenario: str
    confidence: float


def test_fake_gateway_streams_deterministic_text_and_logs_usage(tmp_path) -> None:
    database_path = tmp_path / "model.db"
    repository = ModelCallRepository(database_path)

    async def exercise() -> list[object]:
        await repository.initialize()
        gateway = FakeModelGateway(repository=repository)
        request = ModelRequest(
            request_id="request-fake-001",
            conversation_id="conversation-fake-001",
            messages=[
                ModelMessage(
                    role="user",
                    content=f"问题\n{VERIFIED_RESPONSE_MARKER}\n这是经过业务核验的回答。",
                )
            ],
        )
        return [event async for event in gateway.stream_chat(request)]

    events = asyncio.run(exercise())

    assert "".join(event.delta for event in events if isinstance(event, TextDelta)) == "这是经过业务核验的回答。"
    assert isinstance(events[-2], Usage)
    assert isinstance(events[-1], Completed)
    with sqlite3.connect(database_path) as database:
        row = database.execute(
            "SELECT provider, model, status, request_id, total_tokens FROM model_calls"
        ).fetchone()
    assert row is not None
    assert row[:4] == ("fake", "fake-support-v1", "completed", "request-fake-001")
    assert row[4] > 0


def test_fake_gateway_returns_validated_structured_result(tmp_path) -> None:
    repository = ModelCallRepository(tmp_path / "structured.db")

    async def exercise() -> Classification:
        await repository.initialize()
        gateway = FakeModelGateway(
            repository=repository,
            structured_payload={"scenario": "billing", "confidence": 0.98},
        )
        return await gateway.complete_structured(
            ModelRequest(messages=[ModelMessage(role="user", content="费用不对")]),
            Classification,
        )

    result = asyncio.run(exercise())
    assert result == Classification(scenario="billing", confidence=0.98)
