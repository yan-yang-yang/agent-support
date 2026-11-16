from __future__ import annotations

import asyncio
import json
from collections.abc import AsyncIterator
from typing import Any

import httpx
from pydantic import BaseModel, ValidationError

from .protocol import ModelGatewayError, StructuredT
from .repository import ModelCallRepository
from .types import (
    Completed,
    ModelEvent,
    ModelRequest,
    TextDelta,
    ToolCallDelta,
    Usage,
)


class OpenAICompatibleAdapter:
    provider_name = "openai-compatible"

    def __init__(
        self,
        *,
        base_url: str,
        api_key: str,
        model: str,
        repository: ModelCallRepository,
        timeout_seconds: float = 30,
        max_retries: int = 2,
        retry_delay_seconds: float = 0.25,
        temperature: float | None = None,
        max_output_tokens: int | None = None,
        transport: httpx.AsyncBaseTransport | None = None,
    ) -> None:
        self.model_name = model
        self._repository = repository
        self._max_retries = max_retries
        self._retry_delay_seconds = retry_delay_seconds
        self._temperature = temperature
        self._max_output_tokens = max_output_tokens
        self._client = httpx.AsyncClient(
            base_url=f"{base_url.rstrip('/')}/",
            headers={
                "Authorization": f"Bearer {api_key}",
                "Content-Type": "application/json",
            },
            timeout=timeout_seconds,
            transport=transport,
        )

    async def close(self) -> None:
        await self._client.aclose()

    async def stream_chat(self, request: ModelRequest) -> AsyncIterator[ModelEvent]:
        call = await self._repository.start(
            provider=self.provider_name,
            model=self.model_name,
            request_id=request.request_id,
            conversation_id=request.conversation_id,
        )
        usage: Usage | None = None
        finish_reason = "stop"
        emitted_output = False
        finalized = False

        try:
            for attempt in range(self._max_retries + 1):
                try:
                    async with self._client.stream(
                        "POST",
                        "chat/completions",
                        json=self._request_body(request, stream=True),
                    ) as response:
                        if response.is_error:
                            raise await self._status_error(response)

                        async for line in response.aiter_lines():
                            if not line.startswith("data:"):
                                continue
                            raw_data = line.removeprefix("data:").strip()
                            if not raw_data or raw_data == "[DONE]":
                                continue
                            payload = self._parse_json(raw_data)
                            if payload.get("error"):
                                raise ModelGatewayError(
                                    "Model provider returned a stream error",
                                    safe_code="PROVIDER_STREAM_ERROR",
                                    retryable=False,
                                )

                            raw_usage = payload.get("usage")
                            if raw_usage:
                                usage = self._usage(raw_usage)
                                yield usage

                            for choice in payload.get("choices") or []:
                                if choice.get("finish_reason"):
                                    finish_reason = str(choice["finish_reason"])
                                delta = choice.get("delta") or {}
                                content = delta.get("content")
                                if isinstance(content, str) and content:
                                    emitted_output = True
                                    yield TextDelta(content)
                                for tool_call in delta.get("tool_calls") or []:
                                    function = tool_call.get("function") or {}
                                    emitted_output = True
                                    yield ToolCallDelta(
                                        index=int(tool_call.get("index", 0)),
                                        call_id=tool_call.get("id"),
                                        name=function.get("name"),
                                        arguments_delta=str(function.get("arguments") or ""),
                                    )
                    break
                except asyncio.CancelledError:
                    raise
                except (httpx.TimeoutException, httpx.RequestError) as error:
                    normalized = self._transport_error(error)
                    if emitted_output or attempt >= self._max_retries:
                        raise normalized from error
                    await self._retry_pause(attempt)
                except ModelGatewayError as error:
                    if emitted_output or not error.retryable or attempt >= self._max_retries:
                        raise
                    await self._retry_pause(attempt)

            if usage is None:
                usage = Usage(prompt_tokens=0, completion_tokens=0, total_tokens=0)
                yield usage
            await self._repository.complete(call.id, usage=usage, status="completed")
            finalized = True
            yield Completed(finish_reason)
        except asyncio.CancelledError:
            await self._repository.complete(
                call.id,
                usage=usage,
                status="cancelled",
                error_code="CANCELLED",
            )
            finalized = True
            raise
        except ModelGatewayError as error:
            await self._repository.complete(
                call.id,
                usage=usage,
                status="failed",
                error_code=error.safe_code,
            )
            finalized = True
            raise
        except Exception as error:
            normalized = ModelGatewayError(
                "Unexpected model gateway failure",
                safe_code="MODEL_GATEWAY_ERROR",
                retryable=False,
            )
            await self._repository.complete(
                call.id,
                usage=usage,
                status="failed",
                error_code=normalized.safe_code,
            )
            finalized = True
            raise normalized from error
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
        usage: Usage | None = None
        try:
            body = self._request_body(request, stream=False)
            body["response_format"] = {
                "type": "json_schema",
                "json_schema": {
                    "name": self._schema_name(schema),
                    "strict": True,
                    "schema": self._strict_schema(schema.model_json_schema()),
                },
            }
            response = await self._post_with_retry(body)
            payload = self._parse_json(response.text)
            if payload.get("usage"):
                usage = self._usage(payload["usage"])
            choices = payload.get("choices") or []
            if not choices:
                raise ModelGatewayError(
                    "Model provider returned no structured response",
                    safe_code="PROVIDER_INVALID_RESPONSE",
                    retryable=False,
                )
            message = choices[0].get("message") or {}
            if message.get("refusal"):
                raise ModelGatewayError(
                    "Model refused the structured request",
                    safe_code="MODEL_REFUSAL",
                    retryable=False,
                )
            content = message.get("content")
            if not isinstance(content, str):
                raise ModelGatewayError(
                    "Model provider returned invalid structured content",
                    safe_code="PROVIDER_INVALID_RESPONSE",
                    retryable=False,
                )
            result = schema.model_validate_json(content)
            await self._repository.complete(call.id, usage=usage, status="completed")
            return result
        except ValidationError as error:
            normalized = ModelGatewayError(
                "Model output did not match the required schema",
                safe_code="INVALID_STRUCTURED_OUTPUT",
                retryable=False,
            )
            await self._repository.complete(
                call.id,
                usage=usage,
                status="failed",
                error_code=normalized.safe_code,
            )
            raise normalized from error
        except ModelGatewayError as error:
            await self._repository.complete(
                call.id,
                usage=usage,
                status="failed",
                error_code=error.safe_code,
            )
            raise

    async def _post_with_retry(self, body: dict[str, Any]) -> httpx.Response:
        for attempt in range(self._max_retries + 1):
            try:
                response = await self._client.post("chat/completions", json=body)
                if response.is_error:
                    raise await self._status_error(response)
                return response
            except asyncio.CancelledError:
                raise
            except (httpx.TimeoutException, httpx.RequestError) as error:
                normalized = self._transport_error(error)
                if attempt >= self._max_retries:
                    raise normalized from error
                await self._retry_pause(attempt)
            except ModelGatewayError as error:
                if not error.retryable or attempt >= self._max_retries:
                    raise
                await self._retry_pause(attempt)
        raise AssertionError("Retry loop exited unexpectedly")

    def _request_body(self, request: ModelRequest, *, stream: bool) -> dict[str, Any]:
        body: dict[str, Any] = {
            "model": self.model_name,
            "messages": [message.model_dump(exclude_none=True) for message in request.messages],
            "stream": stream,
        }
        temperature = request.temperature if request.temperature is not None else self._temperature
        max_tokens = (
            request.max_output_tokens
            if request.max_output_tokens is not None
            else self._max_output_tokens
        )
        if temperature is not None:
            body["temperature"] = temperature
        if max_tokens is not None:
            body["max_tokens"] = max_tokens
        if stream:
            body["stream_options"] = {"include_usage": True}
        if request.tools:
            body["tools"] = [
                {
                    "type": "function",
                    "function": {
                        "name": tool.name,
                        "description": tool.description,
                        "parameters": tool.parameters,
                        "strict": tool.strict,
                    },
                }
                for tool in request.tools
            ]
            body["tool_choice"] = "auto"
        return body

    async def _status_error(self, response: httpx.Response) -> ModelGatewayError:
        await response.aread()
        retryable = response.status_code in {408, 409, 429} or response.status_code >= 500
        return ModelGatewayError(
            f"Model provider request failed with status {response.status_code}",
            safe_code=("PROVIDER_UNAVAILABLE" if retryable else "PROVIDER_REQUEST_REJECTED"),
            retryable=retryable,
            status_code=response.status_code,
        )

    @staticmethod
    def _transport_error(error: Exception) -> ModelGatewayError:
        if isinstance(error, httpx.TimeoutException):
            return ModelGatewayError(
                "Model provider timeout",
                safe_code="PROVIDER_TIMEOUT",
                retryable=True,
            )
        return ModelGatewayError(
            "Model provider unavailable",
            safe_code="PROVIDER_UNAVAILABLE",
            retryable=True,
        )

    async def _retry_pause(self, attempt: int) -> None:
        await asyncio.sleep(self._retry_delay_seconds * (2**attempt))

    @staticmethod
    def _parse_json(raw_data: str) -> dict[str, Any]:
        try:
            payload = json.loads(raw_data)
        except json.JSONDecodeError as error:
            raise ModelGatewayError(
                "Model provider returned invalid JSON",
                safe_code="PROVIDER_INVALID_RESPONSE",
                retryable=False,
            ) from error
        if not isinstance(payload, dict):
            raise ModelGatewayError(
                "Model provider returned an invalid payload",
                safe_code="PROVIDER_INVALID_RESPONSE",
                retryable=False,
            )
        return payload

    @staticmethod
    def _usage(payload: dict[str, Any]) -> Usage:
        return Usage(
            prompt_tokens=int(payload.get("prompt_tokens") or 0),
            completion_tokens=int(payload.get("completion_tokens") or 0),
            total_tokens=int(payload.get("total_tokens") or 0),
        )

    @staticmethod
    def _schema_name(schema: type[BaseModel]) -> str:
        return "".join(character if character.isalnum() else "_" for character in schema.__name__)[:64]

    @classmethod
    def _strict_schema(cls, schema: dict[str, Any]) -> dict[str, Any]:
        result = dict(schema)
        if result.get("type") == "object":
            properties = result.get("properties") or {}
            result["properties"] = {
                key: cls._strict_schema(value) if isinstance(value, dict) else value
                for key, value in properties.items()
            }
            result["required"] = list(properties)
            result["additionalProperties"] = False
        if result.get("type") == "array" and isinstance(result.get("items"), dict):
            result["items"] = cls._strict_schema(result["items"])
        for keyword in ("anyOf", "oneOf", "allOf"):
            if isinstance(result.get(keyword), list):
                result[keyword] = [
                    cls._strict_schema(item) if isinstance(item, dict) else item
                    for item in result[keyword]
                ]
        if isinstance(result.get("$defs"), dict):
            result["$defs"] = {
                key: cls._strict_schema(value) if isinstance(value, dict) else value
                for key, value in result["$defs"].items()
            }
        return result
