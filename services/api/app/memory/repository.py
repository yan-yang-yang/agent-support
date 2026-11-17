from __future__ import annotations

from datetime import UTC, datetime
from pathlib import Path

import aiosqlite

from .types import ConversationMemory, MemoryKey, UserMemory


class MemoryRepository:
    def __init__(self, database_path: Path) -> None:
        self.database_path = database_path

    async def initialize(self) -> None:
        self.database_path.parent.mkdir(parents=True, exist_ok=True)
        async with aiosqlite.connect(self.database_path) as database:
            await database.execute("PRAGMA foreign_keys=ON")
            await database.executescript(
                """
                CREATE TABLE IF NOT EXISTS conversation_memories (
                    conversation_id TEXT PRIMARY KEY,
                    user_id TEXT NOT NULL,
                    summary TEXT NOT NULL,
                    summarized_message_count INTEGER NOT NULL DEFAULT 0,
                    summarized_through_message_id TEXT,
                    revision INTEGER NOT NULL DEFAULT 1,
                    created_at TEXT NOT NULL,
                    updated_at TEXT NOT NULL,
                    FOREIGN KEY(conversation_id) REFERENCES conversations(id) ON DELETE CASCADE
                );

                CREATE INDEX IF NOT EXISTS idx_conversation_memories_user
                    ON conversation_memories(user_id, updated_at DESC);

                CREATE TABLE IF NOT EXISTS user_memories (
                    user_id TEXT NOT NULL,
                    memory_key TEXT NOT NULL,
                    memory_value TEXT NOT NULL,
                    source_conversation_id TEXT NOT NULL,
                    source_message_id TEXT NOT NULL,
                    confidence REAL NOT NULL,
                    created_at TEXT NOT NULL,
                    updated_at TEXT NOT NULL,
                    PRIMARY KEY(user_id, memory_key)
                );

                CREATE INDEX IF NOT EXISTS idx_user_memories_updated
                    ON user_memories(user_id, updated_at DESC);
                """
            )
            await database.commit()

    async def get_conversation_memory(
        self,
        conversation_id: str,
        user_id: str,
    ) -> ConversationMemory | None:
        async with aiosqlite.connect(self.database_path) as database:
            database.row_factory = aiosqlite.Row
            cursor = await database.execute(
                """
                SELECT * FROM conversation_memories
                WHERE conversation_id = ? AND user_id = ?
                """,
                (conversation_id, user_id),
            )
            row = await cursor.fetchone()
        return self._conversation_from_row(row) if row else None

    async def save_conversation_summary(
        self,
        *,
        conversation_id: str,
        user_id: str,
        summary: str,
        summarized_message_count: int,
        summarized_through_message_id: str | None,
    ) -> None:
        now = datetime.now(UTC).isoformat()
        async with aiosqlite.connect(self.database_path) as database:
            await database.execute(
                """
                INSERT INTO conversation_memories(
                    conversation_id, user_id, summary, summarized_message_count,
                    summarized_through_message_id, revision, created_at, updated_at
                ) VALUES (?, ?, ?, ?, ?, 1, ?, ?)
                ON CONFLICT(conversation_id) DO UPDATE SET
                    summary = excluded.summary,
                    summarized_message_count = excluded.summarized_message_count,
                    summarized_through_message_id = excluded.summarized_through_message_id,
                    revision = conversation_memories.revision + 1,
                    updated_at = excluded.updated_at
                WHERE conversation_memories.user_id = excluded.user_id
                """,
                (
                    conversation_id,
                    user_id,
                    summary,
                    summarized_message_count,
                    summarized_through_message_id,
                    now,
                    now,
                ),
            )
            await database.commit()

    async def upsert_user_memory(
        self,
        *,
        user_id: str,
        key: MemoryKey,
        value: str,
        source_conversation_id: str,
        source_message_id: str,
        confidence: float,
    ) -> None:
        now = datetime.now(UTC).isoformat()
        async with aiosqlite.connect(self.database_path) as database:
            await database.execute(
                """
                INSERT INTO user_memories(
                    user_id, memory_key, memory_value, source_conversation_id,
                    source_message_id, confidence, created_at, updated_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                ON CONFLICT(user_id, memory_key) DO UPDATE SET
                    memory_value = excluded.memory_value,
                    source_conversation_id = excluded.source_conversation_id,
                    source_message_id = excluded.source_message_id,
                    confidence = excluded.confidence,
                    updated_at = excluded.updated_at
                """,
                (
                    user_id,
                    key,
                    value,
                    source_conversation_id,
                    source_message_id,
                    confidence,
                    now,
                    now,
                ),
            )
            await database.commit()

    async def list_user_memories(self, user_id: str, limit: int = 12) -> list[UserMemory]:
        async with aiosqlite.connect(self.database_path) as database:
            database.row_factory = aiosqlite.Row
            cursor = await database.execute(
                """
                SELECT * FROM user_memories
                WHERE user_id = ?
                ORDER BY updated_at DESC, memory_key ASC
                LIMIT ?
                """,
                (user_id, limit),
            )
            rows = await cursor.fetchall()
        return [self._user_memory_from_row(row) for row in rows]

    async def delete_user_memories(self, user_id: str) -> int:
        async with aiosqlite.connect(self.database_path) as database:
            cursor = await database.execute(
                "DELETE FROM user_memories WHERE user_id = ?",
                (user_id,),
            )
            await database.commit()
            return max(0, cursor.rowcount)

    @staticmethod
    def _conversation_from_row(row: aiosqlite.Row) -> ConversationMemory:
        return ConversationMemory(
            conversation_id=row["conversation_id"],
            user_id=row["user_id"],
            summary=row["summary"],
            summarized_message_count=row["summarized_message_count"],
            summarized_through_message_id=row["summarized_through_message_id"],
            revision=row["revision"],
            created_at=datetime.fromisoformat(row["created_at"]),
            updated_at=datetime.fromisoformat(row["updated_at"]),
        )

    @staticmethod
    def _user_memory_from_row(row: aiosqlite.Row) -> UserMemory:
        return UserMemory(
            user_id=row["user_id"],
            key=row["memory_key"],
            value=row["memory_value"],
            source_conversation_id=row["source_conversation_id"],
            source_message_id=row["source_message_id"],
            confidence=row["confidence"],
            created_at=datetime.fromisoformat(row["created_at"]),
            updated_at=datetime.fromisoformat(row["updated_at"]),
        )
