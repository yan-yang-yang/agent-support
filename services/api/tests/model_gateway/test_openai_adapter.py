from __future__ import annotations

import asyncio
import json
import sqlite3

import httpx
import pytest
from pydantic import BaseModel

from app.model_gateway.openai_adapter import OpenAICompatibleAdapter
from app.model_gateway.protocol import ModelGatewayError
from app.model_gateway.repository import ModelCallRepository
from app.model_gateway.types import (
    Completed,
    ModelMessage,
    ModelRequest,
    TextDelta,
    ToolCallDelta,
    ToolDefinition,
    Usage,
)


def test_stream_normalizes_text_tool_usage_and_completion_events(tmp_path) -> None:
    captured_body: dict[str, object] = {}

    def handler(request: httpx.Request) -> httpx.Response:
        assert request.url.path == "/v1/chat/completions"
        assert request.headers["Authorization"] == "Bearer test-key"
        captured_body.update(json.loads(request.content))
        stream = "\n\n".join(
            [
                'data: {"choices":[{"delta":{"content":"正在查询"},"finish_reason":null}]}',
                'data: {"choices":[{"delta":{"tool_calls":[{"index":0,"id":"call-1","function":{"name":"get_station_status","arguments":"{\\"station_id\\":\\""}}]},"finish_reason":null}]}',
                'data: {"choices":[{"delta":{"tool_calls":[{"index":0,"function":{"arguments":"station-1\\"}"}}]},"finish_reason":"tool_calls"}]}',
                'data: {"choices":[],"usage":{"prompt_tokens":20,"completion_tokens":8,"total_tokens":28}}',
                "data: [DONE]",
            ]
        )
        return httpx.Response(200, text=f"{stream}\n\n", headers={"Content-Type": "text/event-stream"})

    async def exercise() -> list[object]:
        repository = ModelCallRepository(tmp_path / "stream.db")
        await repository.initialize()
        gateway = OpenAICompatibleAdapter(
            base_url="http://provider.test/v1",
            api_key="test-key",
            model="provider-model",
            repository=repository,
            max_retries=0,
            transport=httpx.MockTransport(handler),
        )
        try:
            request = ModelRequest(
                messages=[ModelMessage(role="user", content="查询网点")],
                tools=[
                    ToolDefinition(
                        name="get_station_status",
                        description="查询网点状态",
                        parameters={
                            "type": "object",
                            "properties": {"station_id": {"type": "string"}},
                            "required": ["station_id"],
                            "additionalProperties": False,
                        },
                    )
                ],
            )
            return [event async for event in gateway.stream_chat(request)]
        finally:
            await gateway.close()

    events = asyncio.run(exercise())

    assert [event.kind for event in events] == [
        "text_delta",
        "tool_call_delta",
        "tool_call_delta",
        "usage",
        "completed",
    ]
    assert isinstance(events[0], TextDelta)
    assert isinstance(events[1], ToolCallDelta)
    assert isinstance(events[-2], Usage)
    assert events[-2].total_tokens == 28
    assert isinstance(events[-1], Completed)
    assert events[-1].finish_reason == "tool_calls"
    assert captured_body["model"] == "provider-model"
    assert captured_body["stream_options"] == {"include_usage": True}
    assert captured_body["tool_choice"] == "auto"


def test_provider_timeout_is_retried_and_normalized(tmp_path) -> None:
    attempts = 0

    def handler(request: httpx.Request) -> httpx.Response:
        nonlocal attempts
        attempts += 1
        raise httpx.ReadTimeout("provider is slow", request=request)

    database_path = tmp_path / "timeout.db"

    async def exercise() -> None:
        repository = ModelCallRepository(database_path)
        await repository.initialize()
        gateway = OpenAICompatibleAdapter(
            base_url="http://provider.test/v1",
            api_key="test-key",
            model="provider-model",
            repository=repository,
            max_retries=1,
            retry_delay_seconds=0,
            transport=httpx.MockTransport(handler),
        )
        try:
            with pytest.raises(ModelGatewayError) as captured:
                _ = [
                    event
                    async for event in gateway.stream_chat(
                        ModelRequest(messages=[ModelMessage(role="user", content="你好")])
                    )
                ]
            assert captured.value.safe_code == "PROVIDER_TIMEOUT"
            assert captured.value.retryable is True
        finally:
            await gateway.close()

    asyncio.run(exercise())

    assert attempts == 2
    with sqlite3.connect(database_path) as database:
        row = database.execute("SELECT status, error_code FROM model_calls").fetchone()
    assert row == ("failed", "PROVIDER_TIMEOUT")


class IntentResult(BaseModel):
    scenario: str
    confidence: float


def test_structured_completion_uses_json_schema_and_validates_result(tmp_path) -> None:
    captured_body: dict[str, object] = {}

    def handler(request: httpx.Request) -> httpx.Response:
        captured_body.update(json.loads(request.content))
        return httpx.Response(
            200,
            json={
                "choices": [
                    {
                        "message": {
                            "role": "assistant",
                            "content": '{"scenario":"return_failure","confidence":0.97}',
                        }
                    }
                ],
                "usage": {"prompt_tokens": 12, "completion_tokens": 9, "total_tokens": 21},
            },
        )

    async def exercise() -> IntentResult:
        repository = ModelCallRepository(tmp_path / "structured.db")
        await repository.initialize()
        gateway = OpenAICompatibleAdapter(
            base_url="http://provider.test/v1",
            api_key="test-key",
            model="provider-model",
            repository=repository,
            max_retries=0,
            transport=httpx.MockTransport(handler),
        )
        try:
            return await gateway.complete_structured(
                ModelRequest(messages=[ModelMessage(role="user", content="伞插不进去")]),
                IntentResult,
            )
        finally:
            await gateway.close()

    result = asyncio.run(exercise())

    assert result == IntentResult(scenario="return_failure", confidence=0.97)
    response_format = captured_body["response_format"]
    assert response_format["type"] == "json_schema"
    assert response_format["json_schema"]["strict"] is True
    assert response_format["json_schema"]["schema"]["additionalProperties"] is False
