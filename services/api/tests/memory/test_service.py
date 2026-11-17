from __future__ import annotations

import asyncio

from app.memory.repository import MemoryRepository
from app.memory.service import MemoryService
from app.repository import SQLiteConversationRepository


def run(coroutine):
    return asyncio.run(coroutine)


def build_service(tmp_path, *, recent_message_limit: int = 2, summary_max_chars: int = 500):
    database_path = tmp_path / "memory.db"
    conversations = SQLiteConversationRepository(database_path)
    memories = MemoryRepository(database_path)

    async def initialize():
        await conversations.initialize()
        await memories.initialize()

    run(initialize())
    return (
        conversations,
        memories,
        MemoryService(
            repository=memories,
            conversation_repository=conversations,
            recent_message_limit=recent_message_limit,
            summary_max_chars=summary_max_chars,
        ),
    )


def test_compacts_old_messages_but_keeps_complete_history(tmp_path) -> None:
    conversations, memories, service = build_service(tmp_path)

    async def scenario():
        conversation = await conversations.create_conversation("user-a")
        for index in range(3):
            await conversations.append_message(
                conversation.id,
                "user-a",
                "user",
                f"第 {index + 1} 个用户问题",
            )
            await conversations.append_message(
                conversation.id,
                "user-a",
                "assistant",
                f"第 {index + 1} 个客服回复",
            )
        await service.compact_conversation(user_id="user-a", conversation_id=conversation.id)
        history = await conversations.list_messages(conversation.id, "user-a")
        context = await service.build_context(user_id="user-a", conversation_id=conversation.id)
        summary = await memories.get_conversation_memory(conversation.id, "user-a")
        return history, context, summary

    history, context, summary = run(scenario())

    assert len(history) == 6
    assert [message.content for message in context.recent_messages] == [
        "第 3 个用户问题",
        "第 3 个客服回复",
    ]
    assert summary is not None
    assert summary.summarized_message_count == 4
    assert "第 1 个用户问题" in summary.summary
    assert "第 2 个客服回复" in summary.summary
    assert "第 3 个用户问题" not in summary.summary


def test_extracts_only_allowlisted_preferences_and_updates_existing_key(tmp_path) -> None:
    conversations, memories, service = build_service(tmp_path)

    async def scenario():
        first = await conversations.create_conversation("user-a")
        first_message = await conversations.append_message(
            first.id,
            "user-a",
            "user",
            "以后叫我小杨，我的常用网点是软件园 A 口站，回复简短一点",
        )
        await service.capture_user_message(
            user_id="user-a",
            conversation_id=first.id,
            message_id=first_message.id,
            content=first_message.content,
        )
        unsafe = await conversations.append_message(
            first.id,
            "user-a",
            "user",
            "记住我的手机号是13800138000，银行卡是6222021234567890",
        )
        await service.capture_user_message(
            user_id="user-a",
            conversation_id=first.id,
            message_id=unsafe.id,
            content=unsafe.content,
        )
        second = await conversations.create_conversation("user-a")
        update = await conversations.append_message(
            second.id,
            "user-a",
            "user",
            "以后叫我杨先生",
        )
        await service.capture_user_message(
            user_id="user-a",
            conversation_id=second.id,
            message_id=update.id,
            content=update.content,
        )
        return await memories.list_user_memories("user-a")

    stored = run(scenario())
    values = {item.key: item.value for item in stored}

    assert values == {
        "preferred_name": "杨先生",
        "response_style": "简洁",
        "frequent_station": "软件园 A 口站",
    }
    assert all("13800138000" not in item.value for item in stored)
    assert all("622202" not in item.value for item in stored)


def test_long_term_memory_is_scoped_by_current_user(tmp_path) -> None:
    conversations, memories, service = build_service(tmp_path)

    async def scenario():
        conversation = await conversations.create_conversation("user-a")
        message = await conversations.append_message(
            conversation.id,
            "user-a",
            "user",
            "以后叫我小杨",
        )
        await service.capture_user_message(
            user_id="user-a",
            conversation_id=conversation.id,
            message_id=message.id,
            content=message.content,
        )
        return (
            await memories.list_user_memories("user-a"),
            await memories.list_user_memories("user-b"),
        )

    user_a, user_b = run(scenario())
    assert [(item.key, item.value) for item in user_a] == [("preferred_name", "小杨")]
    assert user_b == []
