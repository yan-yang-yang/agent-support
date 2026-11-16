from __future__ import annotations

import json
from datetime import UTC, datetime
from pathlib import Path
from typing import Any
from uuid import uuid4

import aiosqlite

from .schemas import ConversationDTO, MessageDTO


def utc_now() -> datetime:
    return datetime.now(UTC)


class ConversationNotFoundError(LookupError):
    pass


class SQLiteConversationRepository:
    def __init__(self, database_path: Path) -> None:
        self.database_path = database_path

    async def initialize(self) -> None:
        self.database_path.parent.mkdir(parents=True, exist_ok=True)
        async with aiosqlite.connect(self.database_path) as database:
            await database.execute("PRAGMA journal_mode=WAL")
            await database.execute("PRAGMA foreign_keys=ON")
            await database.executescript(
                """
                CREATE TABLE IF NOT EXISTS conversations (
                    id TEXT PRIMARY KEY,
                    user_id TEXT NOT NULL,
                    title TEXT NOT NULL,
                    created_at TEXT NOT NULL,
                    updated_at TEXT NOT NULL
                );

                CREATE INDEX IF NOT EXISTS idx_conversations_user_updated
                    ON conversations(user_id, updated_at DESC);

                CREATE TABLE IF NOT EXISTS messages (
                    id TEXT PRIMARY KEY,
                    conversation_id TEXT NOT NULL,
                    role TEXT NOT NULL CHECK(role IN ('user', 'assistant')),
                    content TEXT NOT NULL,
                    card_json TEXT,
                    request_id TEXT,
                    created_at TEXT NOT NULL,
                    FOREIGN KEY(conversation_id) REFERENCES conversations(id) ON DELETE CASCADE
                );

                CREATE INDEX IF NOT EXISTS idx_messages_conversation_created
                    ON messages(conversation_id, created_at ASC);
                """
            )
            await database.commit()

    async def create_conversation(self, user_id: str, title: str | None = None) -> ConversationDTO:
        conversation_id = str(uuid4())
        now = utc_now()
        safe_title = title.strip() if title and title.strip() else "新会话"
        async with aiosqlite.connect(self.database_path) as database:
            await database.execute(
                "INSERT INTO conversations(id, user_id, title, created_at, updated_at) VALUES (?, ?, ?, ?, ?)",
                (conversation_id, user_id, safe_title, now.isoformat(), now.isoformat()),
            )
            await database.commit()
        return ConversationDTO(
            id=conversation_id,
            title=safe_title,
            preview="开始新的客服咨询",
            created_at=now,
            updated_at=now,
            message_count=0,
        )

    async def require_conversation(self, conversation_id: str, user_id: str) -> None:
        async with aiosqlite.connect(self.database_path) as database:
            cursor = await database.execute(
                "SELECT 1 FROM conversations WHERE id = ? AND user_id = ?",
                (conversation_id, user_id),
            )
            row = await cursor.fetchone()
        if row is None:
            raise ConversationNotFoundError(conversation_id)

    async def list_conversations(self, user_id: str) -> list[ConversationDTO]:
        async with aiosqlite.connect(self.database_path) as database:
            database.row_factory = aiosqlite.Row
            cursor = await database.execute(
                """
                SELECT
                    c.id,
                    c.title,
                    c.created_at,
                    c.updated_at,
                    COUNT(m.id) AS message_count,
                    COALESCE(
                        (SELECT content FROM messages latest
                         WHERE latest.conversation_id = c.id
                         ORDER BY latest.created_at DESC, latest.rowid DESC LIMIT 1),
                        '开始新的客服咨询'
                    ) AS preview
                FROM conversations c
                LEFT JOIN messages m ON m.conversation_id = c.id
                WHERE c.user_id = ?
                GROUP BY c.id
                ORDER BY c.updated_at DESC
                """,
                (user_id,),
            )
            rows = await cursor.fetchall()
        return [
            ConversationDTO(
                id=row["id"],
                title=row["title"],
                preview=row["preview"],
                created_at=datetime.fromisoformat(row["created_at"]),
                updated_at=datetime.fromisoformat(row["updated_at"]),
                message_count=row["message_count"],
            )
            for row in rows
        ]

    async def list_messages(self, conversation_id: str, user_id: str) -> list[MessageDTO]:
        await self.require_conversation(conversation_id, user_id)
        async with aiosqlite.connect(self.database_path) as database:
            database.row_factory = aiosqlite.Row
            cursor = await database.execute(
                """
                SELECT id, conversation_id, role, content, card_json, created_at
                FROM messages
                WHERE conversation_id = ?
                ORDER BY created_at ASC, rowid ASC
                """,
                (conversation_id,),
            )
            rows = await cursor.fetchall()
        return [self._message_from_row(row) for row in rows]

    async def append_message(
        self,
        conversation_id: str,
        user_id: str,
        role: str,
        content: str,
        *,
        card: dict[str, Any] | None = None,
        request_id: str | None = None,
        message_id: str | None = None,
    ) -> MessageDTO:
        await self.require_conversation(conversation_id, user_id)
        now = utc_now()
        resolved_id = message_id or str(uuid4())
        async with aiosqlite.connect(self.database_path) as database:
            await database.execute(
                """
                INSERT INTO messages(id, conversation_id, role, content, card_json, request_id, created_at)
                VALUES (?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    resolved_id,
                    conversation_id,
                    role,
                    content,
                    json.dumps(card, ensure_ascii=False) if card else None,
                    request_id,
                    now.isoformat(),
                ),
            )
            if role == "user":
                title = self._title_from_message(content)
                await database.execute(
                    """
                    UPDATE conversations
                    SET title = CASE WHEN title = '新会话' THEN ? ELSE title END,
                        updated_at = ?
                    WHERE id = ?
                    """,
                    (title, now.isoformat(), conversation_id),
                )
            else:
                await database.execute(
                    "UPDATE conversations SET updated_at = ? WHERE id = ?",
                    (now.isoformat(), conversation_id),
                )
            await database.commit()
        return MessageDTO(
            id=resolved_id,
            conversation_id=conversation_id,
            role=role,
            content=content,
            card=card,
            created_at=now,
        )

    @staticmethod
    def _title_from_message(content: str) -> str:
        compact = " ".join(content.split())
        return compact if len(compact) <= 18 else f"{compact[:18]}…"

    @staticmethod
    def _message_from_row(row: aiosqlite.Row) -> MessageDTO:
        return MessageDTO(
            id=row["id"],
            conversation_id=row["conversation_id"],
            role=row["role"],
            content=row["content"],
            card=json.loads(row["card_json"]) if row["card_json"] else None,
            created_at=datetime.fromisoformat(row["created_at"]),
        )
