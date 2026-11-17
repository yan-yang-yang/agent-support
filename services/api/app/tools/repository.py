from __future__ import annotations

import json
from datetime import UTC, datetime
from pathlib import Path
from typing import Any
from uuid import uuid4

import aiosqlite


class ToolCallRepository:
    def __init__(self, database_path: Path) -> None:
        self.database_path = database_path

    async def initialize(self) -> None:
        self.database_path.parent.mkdir(parents=True, exist_ok=True)
        async with aiosqlite.connect(self.database_path) as database:
            await database.execute(
                """
                CREATE TABLE IF NOT EXISTS tool_calls (
                    id TEXT PRIMARY KEY,
                    request_id TEXT NOT NULL,
                    conversation_id TEXT NOT NULL,
                    user_id TEXT NOT NULL,
                    tool_name TEXT NOT NULL,
                    arguments_json TEXT NOT NULL,
                    result_json TEXT,
                    status TEXT NOT NULL,
                    error_code TEXT,
                    retryable INTEGER NOT NULL DEFAULT 0,
                    latency_ms INTEGER,
                    created_at TEXT NOT NULL,
                    completed_at TEXT
                )
                """
            )
            await database.execute(
                "CREATE INDEX IF NOT EXISTS idx_tool_calls_request ON tool_calls(request_id, created_at)"
            )
            await database.commit()

    async def start(
        self,
        *,
        request_id: str,
        conversation_id: str,
        user_id: str,
        tool_name: str,
        arguments: dict[str, object],
    ) -> str:
        call_id = str(uuid4())
        async with aiosqlite.connect(self.database_path) as database:
            await database.execute(
                """
                INSERT INTO tool_calls(
                    id, request_id, conversation_id, user_id, tool_name,
                    arguments_json, status, created_at
                ) VALUES (?, ?, ?, ?, ?, ?, 'started', ?)
                """,
                (
                    call_id,
                    request_id,
                    conversation_id,
                    user_id,
                    tool_name,
                    json.dumps(arguments, ensure_ascii=False, sort_keys=True),
                    datetime.now(UTC).isoformat(),
                ),
            )
            await database.commit()
        return call_id

    async def complete(
        self,
        call_id: str,
        *,
        status: str,
        result: Any = None,
        error_code: str | None = None,
        retryable: bool = False,
    ) -> None:
        completed_at = datetime.now(UTC)
        async with aiosqlite.connect(self.database_path) as database:
            cursor = await database.execute(
                "SELECT created_at FROM tool_calls WHERE id = ?",
                (call_id,),
            )
            row = await cursor.fetchone()
            if row is None:
                return
            created_at = datetime.fromisoformat(row[0])
            latency_ms = max(0, round((completed_at - created_at).total_seconds() * 1000))
            await database.execute(
                """
                UPDATE tool_calls
                SET result_json = ?, status = ?, error_code = ?, retryable = ?,
                    latency_ms = ?, completed_at = ?
                WHERE id = ?
                """,
                (
                    json.dumps(result, ensure_ascii=False, sort_keys=True) if result is not None else None,
                    status,
                    error_code,
                    int(retryable),
                    latency_ms,
                    completed_at.isoformat(),
                    call_id,
                ),
            )
            await database.commit()
