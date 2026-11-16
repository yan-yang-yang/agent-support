from __future__ import annotations

import asyncio
import json
from collections.abc import AsyncIterator
from typing import Any
from uuid import uuid4

from .business import BusinessGateway
from .model_gateway.protocol import ModelGateway, ModelGatewayError
from .model_gateway.types import VERIFIED_RESPONSE_MARKER, ModelMessage, ModelRequest, TextDelta
from .repository import SQLiteConversationRepository
from .scenarios import progress_labels_for, progress_steps, script_for


def encode_sse(event: str, data: dict[str, Any]) -> str:
    payload = json.dumps(data, ensure_ascii=False, separators=(",", ":"))
    return f"event: {event}\ndata: {payload}\n\n"


async def stream_support_reply(
    *,
    repository: SQLiteConversationRepository,
    business_gateway: BusinessGateway,
    model_gateway: ModelGateway,
    user_id: str,
    conversation_id: str,
    content: str,
    request_id: str,
    character_delay: float,
) -> AsyncIterator[str]:
    assistant_id = str(uuid4())
    user_message = await repository.append_message(
        conversation_id,
        user_id,
        "user",
        content,
        request_id=request_id,
    )

    yield encode_sse(
        "message.started",
        {
            "requestId": request_id,
            "assistantId": assistant_id,
            "message": user_message.model_dump(mode="json"),
        },
    )
    labels = progress_labels_for(content)
    yield encode_sse("progress.updated", {"steps": progress_steps(labels, 0)})

    await asyncio.sleep(0.28)
    yield encode_sse("progress.updated", {"steps": progress_steps(labels, 1)})

    script = await script_for(content, user_id, business_gateway)

    await asyncio.sleep(0.42)
    yield encode_sse("progress.updated", {"steps": progress_steps(script.progress_labels, 2)})

    model_request = ModelRequest(
        request_id=request_id,
        conversation_id=conversation_id,
        messages=[
            ModelMessage(
                role="system",
                content=(
                    "你是公共雨伞客服。只允许使用已核验业务信息回答，不得编造订单、金额、"
                    "网点库存或处理结果；不要承诺退款，不要声称已完成未执行的操作。回答简洁自然。"
                ),
            ),
            ModelMessage(
                role="user",
                content=(
                    f"用户问题：{content}\n\n"
                    f"{VERIFIED_RESPONSE_MARKER}\n{script.response}"
                ),
            ),
        ],
    )
    response_parts: list[str] = []
    try:
        async for model_event in model_gateway.stream_chat(model_request):
            if isinstance(model_event, TextDelta) and model_event.delta:
                response_parts.append(model_event.delta)
                yield encode_sse("assistant.delta", {"delta": model_event.delta})
    except ModelGatewayError:
        separator = "\n\n" if response_parts else ""
        fallback = f"{separator}{script.response}"
        for character in fallback:
            punctuation_pause = 0.055 if character in "，。；！" else 0
            await asyncio.sleep(character_delay + punctuation_pause)
            response_parts.append(character)
            yield encode_sse("assistant.delta", {"delta": character})

    assistant_response = "".join(response_parts).strip()
    if not assistant_response:
        assistant_response = script.response
        for character in assistant_response:
            yield encode_sse("assistant.delta", {"delta": character})

    if script.card is not None:
        yield encode_sse("business_card", {"card": script.card})
    yield encode_sse("progress.updated", {"steps": progress_steps(script.progress_labels, 3)})

    assistant_message = await repository.append_message(
        conversation_id,
        user_id,
        "assistant",
        assistant_response,
        card=script.card,
        request_id=request_id,
        message_id=assistant_id,
    )
    yield encode_sse(
        "assistant.completed",
        {
            "requestId": request_id,
            "message": assistant_message.model_dump(mode="json"),
        },
    )
