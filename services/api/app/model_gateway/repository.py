from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path
from uuid import uuid4

import aiosqlite

from .types import Usage


@dataclass(frozen=True, slots=True)
class ModelCallDTO:
    id: str
    provider: str
    model: str
    request_id: str | None
    conversation_id: str | None
    status: str
    prompt_tokens: int
    completion_tokens: int
    total_tokens: int
    latency_ms: int | None
    error_code: str | None
    created_at: datetime
    completed_at: datetime | None


class ModelCallRepository:
    def __init__(self, database_path: Path) -> None:
        self.database_path = database_path

    async def initialize(self) -> None:
        self.database_path.parent.mkdir(parents=True, exist_ok=True)
        async with aiosqlite.connect(self.database_path) as database:
            await database.execute(
                """
                CREATE TABLE IF NOT EXISTS model_calls (
                    id TEXT PRIMARY KEY,
                    provider TEXT NOT NULL,
                    model TEXT NOT NULL,
                    request_id TEXT,
                    conversation_id TEXT,
                    status TEXT NOT NULL,
                    prompt_tokens INTEGER NOT NULL DEFAULT 0,
                    completion_tokens INTEGER NOT NULL DEFAULT 0,
                    total_tokens INTEGER NOT NULL DEFAULT 0,
                    latency_ms INTEGER,
                    error_code TEXT,
                    created_at TEXT NOT NULL,
                    completed_at TEXT
                )
                """
            )
            await database.execute(
                "CREATE INDEX IF NOT EXISTS idx_model_calls_request ON model_calls(request_id)"
            )
            await database.commit()

    async def start(
        self,
        *,
        provider: str,
        model: str,
        request_id: str | None,
        conversation_id: str | None,
    ) -> ModelCallDTO:
        call_id = str(uuid4())
        created_at = datetime.now(UTC)
        async with aiosqlite.connect(self.database_path) as database:
            await database.execute(
                """
                INSERT INTO model_calls(
                    id, provider, model, request_id, conversation_id, status, created_at
                ) VALUES (?, ?, ?, ?, ?, 'started', ?)
                """,
                (
                    call_id,
                    provider,
                    model,
                    request_id,
                    conversation_id,
                    created_at.isoformat(),
                ),
            )
            await database.commit()
        return ModelCallDTO(
            id=call_id,
            provider=provider,
            model=model,
            request_id=request_id,
            conversation_id=conversation_id,
            status="started",
            prompt_tokens=0,
            completion_tokens=0,
            total_tokens=0,
            latency_ms=None,
            error_code=None,
            created_at=created_at,
            completed_at=None,
        )

    async def complete(
        self,
        call_id: str,
        *,
        usage: Usage | None,
        status: str,
        error_code: str | None = None,
    ) -> None:
        completed_at = datetime.now(UTC)
        async with aiosqlite.connect(self.database_path) as database:
            cursor = await database.execute(
                "SELECT created_at FROM model_calls WHERE id = ?",
                (call_id,),
            )
            row = await cursor.fetchone()
            if row is None:
                return
            created_at = datetime.fromisoformat(row[0])
            latency_ms = max(0, round((completed_at - created_at).total_seconds() * 1000))
            await database.execute(
                """
                UPDATE model_calls
                SET status = ?, prompt_tokens = ?, completion_tokens = ?, total_tokens = ?,
                    latency_ms = ?, error_code = ?, completed_at = ?
                WHERE id = ?
                """,
                (
                    status,
                    usage.prompt_tokens if usage else 0,
                    usage.completion_tokens if usage else 0,
                    usage.total_tokens if usage else 0,
                    latency_ms,
                    error_code,
                    completed_at.isoformat(),
                    call_id,
                ),
            )
            await database.commit()

    async def get(self, call_id: str) -> ModelCallDTO | None:
        async with aiosqlite.connect(self.database_path) as database:
            database.row_factory = aiosqlite.Row
            cursor = await database.execute(
                "SELECT * FROM model_calls WHERE id = ?",
                (call_id,),
            )
            row = await cursor.fetchone()
        if row is None:
            return None
        return ModelCallDTO(
            id=row["id"],
            provider=row["provider"],
            model=row["model"],
            request_id=row["request_id"],
            conversation_id=row["conversation_id"],
            status=row["status"],
            prompt_tokens=row["prompt_tokens"],
            completion_tokens=row["completion_tokens"],
            total_tokens=row["total_tokens"],
            latency_ms=row["latency_ms"],
            error_code=row["error_code"],
            created_at=datetime.fromisoformat(row["created_at"]),
            completed_at=(
                datetime.fromisoformat(row["completed_at"])
                if row["completed_at"]
                else None
            ),
        )
