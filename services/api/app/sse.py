from __future__ import annotations

import asyncio
import json
from collections.abc import AsyncIterator
from typing import Any
from uuid import uuid4

from .repository import SQLiteConversationRepository
from .scenarios import progress_steps, script_for


def encode_sse(event: str, data: dict[str, Any]) -> str:
    payload = json.dumps(data, ensure_ascii=False, separators=(",", ":"))
    return f"event: {event}\ndata: {payload}\n\n"


async def stream_support_reply(
    *,
    repository: SQLiteConversationRepository,
    user_id: str,
    conversation_id: str,
    content: str,
    request_id: str,
    character_delay: float,
) -> AsyncIterator[str]:
    script = script_for(content)
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
    yield encode_sse("progress.updated", {"steps": progress_steps(script.progress_labels, 0)})

    await asyncio.sleep(0.28)
    yield encode_sse("progress.updated", {"steps": progress_steps(script.progress_labels, 1)})

    await asyncio.sleep(0.42)
    yield encode_sse("progress.updated", {"steps": progress_steps(script.progress_labels, 2)})

    for character in script.response:
        punctuation_pause = 0.055 if character in "，。；！" else 0
        await asyncio.sleep(character_delay + punctuation_pause)
        yield encode_sse("assistant.delta", {"delta": character})

    yield encode_sse("business_card", {"card": script.card})
    yield encode_sse("progress.updated", {"steps": progress_steps(script.progress_labels, 3)})

    assistant_message = await repository.append_message(
        conversation_id,
        user_id,
        "assistant",
        script.response,
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
