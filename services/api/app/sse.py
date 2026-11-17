from __future__ import annotations

import asyncio
import json
from collections.abc import AsyncIterator
from typing import Any
from uuid import uuid4

from .agent.events import AgentCompletedEvent, ToolCompletedEvent, ToolStartedEvent
from .agent.runner import AgentRunner
from .memory.service import MemoryService
from .model_gateway.protocol import ModelGateway, ModelGatewayError
from .model_gateway.types import VERIFIED_RESPONSE_MARKER, ModelMessage, ModelRequest, TextDelta
from .repository import SQLiteConversationRepository


def progress_steps(labels: tuple[str, str, str], active_index: int) -> list[dict[str, str]]:
    return [
        {
            "label": label,
            "state": "complete" if index < active_index else "active" if index == active_index else "pending",
        }
        for index, label in enumerate(labels)
    ]


def encode_sse(event: str, data: dict[str, Any]) -> str:
    payload = json.dumps(data, ensure_ascii=False, separators=(",", ":"))
    return f"event: {event}\ndata: {payload}\n\n"


async def stream_support_reply(
    *,
    repository: SQLiteConversationRepository,
    agent_runner: AgentRunner,
    model_gateway: ModelGateway,
    memory_service: MemoryService,
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
    await memory_service.capture_user_message(
        user_id=user_id,
        conversation_id=conversation_id,
        message_id=user_message.id,
        content=content,
    )
    memory_context = await memory_service.build_context(
        user_id=user_id,
        conversation_id=conversation_id,
        current_message_id=user_message.id,
    )
    prior_user_messages = tuple(
        message.content
        for message in memory_context.recent_messages
        if message.role == "user"
    )

    yield encode_sse(
        "message.started",
        {
            "requestId": request_id,
            "assistantId": assistant_id,
            "message": user_message.model_dump(mode="json"),
        },
    )
    labels = agent_runner.progress_labels(content, prior_user_messages)
    yield encode_sse("progress.updated", {"steps": progress_steps(labels, 0)})

    await asyncio.sleep(0.28)
    yield encode_sse("progress.updated", {"steps": progress_steps(labels, 1)})

    agent_result = None
    async for agent_event in agent_runner.stream_turn(
        user_id=user_id,
        conversation_id=conversation_id,
        request_id=request_id,
        content=content,
        prior_user_messages=prior_user_messages,
    ):
        if isinstance(agent_event, ToolStartedEvent):
            yield encode_sse("tool.started", {"name": agent_event.name})
        elif isinstance(agent_event, ToolCompletedEvent):
            yield encode_sse(
                "tool.completed",
                {
                    "name": agent_event.name,
                    "status": agent_event.status,
                    "callId": agent_event.call_id,
                    "errorCode": agent_event.error_code,
                },
            )
        elif isinstance(agent_event, AgentCompletedEvent):
            agent_result = agent_event.result

    if agent_result is None:
        raise RuntimeError("Agent graph completed without a result")

    await asyncio.sleep(0.42)
    yield encode_sse("progress.updated", {"steps": progress_steps(labels, 2)})

    verified_response = memory_service.personalize(
        agent_result.verified_response,
        memory_context,
    )
    model_request = ModelRequest(
        request_id=request_id,
        conversation_id=conversation_id,
        messages=[
            ModelMessage(
                role="system",
                content=(
                    "你是公共雨伞客服。只允许使用已核验业务信息回答，不得编造订单、金额、"
                    "网点库存或处理结果；不要承诺退款，不要声称已完成未执行的操作。"
                    "可以按照系统上下文中保存的称呼、语言和回复风格调整表达。"
                ),
            ),
            memory_service.context_system_message(memory_context),
            *memory_service.recent_model_messages(memory_context),
            ModelMessage(
                role="user",
                content=(
                    f"用户问题：{content}\n\n"
                    f"{VERIFIED_RESPONSE_MARKER}\n{verified_response}"
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
        fallback = f"{separator}{verified_response}"
        for character in fallback:
            punctuation_pause = 0.055 if character in "，。；！" else 0
            await asyncio.sleep(character_delay + punctuation_pause)
            response_parts.append(character)
            yield encode_sse("assistant.delta", {"delta": character})

    assistant_response = "".join(response_parts).strip()
    if not assistant_response:
        assistant_response = verified_response
        for character in assistant_response:
            yield encode_sse("assistant.delta", {"delta": character})

    if agent_result.card is not None:
        yield encode_sse("business_card", {"card": agent_result.card})
    yield encode_sse("progress.updated", {"steps": progress_steps(labels, 3)})

    assistant_message = await repository.append_message(
        conversation_id,
        user_id,
        "assistant",
        assistant_response,
        card=agent_result.card,
        request_id=request_id,
        message_id=assistant_id,
    )
    await memory_service.compact_conversation(
        user_id=user_id,
        conversation_id=conversation_id,
    )
    yield encode_sse(
        "assistant.completed",
        {
            "requestId": request_id,
            "message": assistant_message.model_dump(mode="json"),
        },
    )
