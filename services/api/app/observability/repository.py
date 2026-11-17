from __future__ import annotations

from datetime import UTC, datetime
from pathlib import Path
from uuid import uuid4

import aiosqlite

from .types import ModelSpan, ToolSpan, TraceDetail, TraceStatus, TraceSummary, TurnTrace


class TraceRepository:
    def __init__(self, database_path: Path) -> None:
        self.database_path = database_path

    async def initialize(self) -> None:
        self.database_path.parent.mkdir(parents=True, exist_ok=True)
        async with aiosqlite.connect(self.database_path) as database:
            await database.execute(
                """
                CREATE TABLE IF NOT EXISTS turn_traces (
                    id TEXT PRIMARY KEY,
                    request_id TEXT NOT NULL,
                    conversation_id TEXT NOT NULL,
                    user_id TEXT NOT NULL,
                    scenario TEXT,
                    status TEXT NOT NULL,
                    safe_fallback INTEGER NOT NULL DEFAULT 0,
                    error_code TEXT,
                    input_chars INTEGER NOT NULL DEFAULT 0,
                    recent_message_count INTEGER NOT NULL DEFAULT 0,
                    summary_used INTEGER NOT NULL DEFAULT 0,
                    long_term_memory_count INTEGER NOT NULL DEFAULT 0,
                    tool_call_count INTEGER NOT NULL DEFAULT 0,
                    tool_success_count INTEGER NOT NULL DEFAULT 0,
                    model_call_count INTEGER NOT NULL DEFAULT 0,
                    model_failure_count INTEGER NOT NULL DEFAULT 0,
                    prompt_tokens INTEGER NOT NULL DEFAULT 0,
                    completion_tokens INTEGER NOT NULL DEFAULT 0,
                    total_tokens INTEGER NOT NULL DEFAULT 0,
                    duration_ms INTEGER,
                    created_at TEXT NOT NULL,
                    completed_at TEXT
                )
                """
            )
            await database.execute(
                "CREATE INDEX IF NOT EXISTS idx_turn_traces_user_created "
                "ON turn_traces(user_id, created_at DESC)"
            )
            await database.execute(
                "CREATE INDEX IF NOT EXISTS idx_turn_traces_request "
                "ON turn_traces(request_id, created_at DESC)"
            )
            await database.commit()

    async def start(
        self,
        *,
        request_id: str,
        conversation_id: str,
        user_id: str,
        input_chars: int,
    ) -> TurnTrace:
        trace_id = str(uuid4())
        created_at = datetime.now(UTC)
        async with aiosqlite.connect(self.database_path) as database:
            await database.execute(
                """
                INSERT INTO turn_traces(
                    id, request_id, conversation_id, user_id, status,
                    input_chars, created_at
                ) VALUES (?, ?, ?, ?, 'started', ?, ?)
                """,
                (
                    trace_id,
                    request_id,
                    conversation_id,
                    user_id,
                    input_chars,
                    created_at.isoformat(),
                ),
            )
            await database.commit()
        return TurnTrace(
            id=trace_id,
            request_id=request_id,
            conversation_id=conversation_id,
            user_id=user_id,
            scenario=None,
            status="started",
            safe_fallback=False,
            error_code=None,
            input_chars=input_chars,
            recent_message_count=0,
            summary_used=False,
            long_term_memory_count=0,
            tool_call_count=0,
            tool_success_count=0,
            model_call_count=0,
            model_failure_count=0,
            prompt_tokens=0,
            completion_tokens=0,
            total_tokens=0,
            duration_ms=None,
            created_at=created_at,
            completed_at=None,
        )

    async def complete(
        self,
        trace_id: str,
        *,
        status: TraceStatus,
        scenario: str | None,
        safe_fallback: bool,
        error_code: str | None,
        recent_message_count: int,
        summary_used: bool,
        long_term_memory_count: int,
    ) -> None:
        completed_at = datetime.now(UTC)
        async with aiosqlite.connect(self.database_path) as database:
            database.row_factory = aiosqlite.Row
            cursor = await database.execute(
                "SELECT request_id, conversation_id, user_id, created_at FROM turn_traces WHERE id = ?",
                (trace_id,),
            )
            trace = await cursor.fetchone()
            if trace is None:
                return
            tool_cursor = await database.execute(
                """
                SELECT
                    COUNT(*) AS call_count,
                    COALESCE(SUM(CASE WHEN status = 'success' THEN 1 ELSE 0 END), 0) AS success_count
                FROM tool_calls
                WHERE request_id = ? AND conversation_id = ? AND user_id = ?
                """,
                (trace["request_id"], trace["conversation_id"], trace["user_id"]),
            )
            tool_metrics = await tool_cursor.fetchone()
            model_cursor = await database.execute(
                """
                SELECT
                    COUNT(*) AS call_count,
                    COALESCE(SUM(CASE WHEN status != 'completed' THEN 1 ELSE 0 END), 0) AS failure_count,
                    COALESCE(SUM(prompt_tokens), 0) AS prompt_tokens,
                    COALESCE(SUM(completion_tokens), 0) AS completion_tokens,
                    COALESCE(SUM(total_tokens), 0) AS total_tokens
                FROM model_calls
                WHERE request_id = ? AND conversation_id = ?
                """,
                (trace["request_id"], trace["conversation_id"]),
            )
            model_metrics = await model_cursor.fetchone()
            created_at = datetime.fromisoformat(trace["created_at"])
            duration_ms = max(0, round((completed_at - created_at).total_seconds() * 1000))
            await database.execute(
                """
                UPDATE turn_traces
                SET scenario = ?, status = ?, safe_fallback = ?, error_code = ?,
                    recent_message_count = ?, summary_used = ?, long_term_memory_count = ?,
                    tool_call_count = ?, tool_success_count = ?,
                    model_call_count = ?, model_failure_count = ?,
                    prompt_tokens = ?, completion_tokens = ?, total_tokens = ?,
                    duration_ms = ?, completed_at = ?
                WHERE id = ?
                """,
                (
                    scenario,
                    status,
                    int(safe_fallback),
                    error_code,
                    recent_message_count,
                    int(summary_used),
                    long_term_memory_count,
                    tool_metrics["call_count"],
                    tool_metrics["success_count"],
                    model_metrics["call_count"],
                    model_metrics["failure_count"],
                    model_metrics["prompt_tokens"],
                    model_metrics["completion_tokens"],
                    model_metrics["total_tokens"],
                    duration_ms,
                    completed_at.isoformat(),
                    trace_id,
                ),
            )
            await database.commit()

    async def list_traces(self, user_id: str, limit: int = 20) -> list[TurnTrace]:
        async with aiosqlite.connect(self.database_path) as database:
            database.row_factory = aiosqlite.Row
            cursor = await database.execute(
                """
                SELECT * FROM turn_traces
                WHERE user_id = ?
                ORDER BY created_at DESC
                LIMIT ?
                """,
                (user_id, limit),
            )
            rows = await cursor.fetchall()
        return [self._trace_from_row(row) for row in rows]

    async def get_detail(self, trace_id: str, user_id: str) -> TraceDetail | None:
        async with aiosqlite.connect(self.database_path) as database:
            database.row_factory = aiosqlite.Row
            cursor = await database.execute(
                "SELECT * FROM turn_traces WHERE id = ? AND user_id = ?",
                (trace_id, user_id),
            )
            row = await cursor.fetchone()
            if row is None:
                return None
            trace = self._trace_from_row(row)
            tool_cursor = await database.execute(
                """
                SELECT id, tool_name, status, error_code, retryable,
                       latency_ms, created_at, completed_at
                FROM tool_calls
                WHERE request_id = ? AND conversation_id = ? AND user_id = ?
                ORDER BY created_at ASC
                """,
                (trace.request_id, trace.conversation_id, trace.user_id),
            )
            tool_rows = await tool_cursor.fetchall()
            model_cursor = await database.execute(
                """
                SELECT id, provider, model, status, error_code, prompt_tokens,
                       completion_tokens, total_tokens, latency_ms, created_at, completed_at
                FROM model_calls
                WHERE request_id = ? AND conversation_id = ?
                ORDER BY created_at ASC
                """,
                (trace.request_id, trace.conversation_id),
            )
            model_rows = await model_cursor.fetchall()
        return TraceDetail(
            trace=trace,
            tool_spans=tuple(self._tool_span_from_row(row) for row in tool_rows),
            model_spans=tuple(self._model_span_from_row(row) for row in model_rows),
        )

    async def summary(self, user_id: str) -> TraceSummary:
        async with aiosqlite.connect(self.database_path) as database:
            database.row_factory = aiosqlite.Row
            cursor = await database.execute(
                """
                SELECT
                    COUNT(*) AS total_turns,
                    COALESCE(SUM(CASE WHEN status = 'completed' THEN 1 ELSE 0 END), 0) AS completed_turns,
                    COALESCE(SUM(CASE WHEN status = 'failed' THEN 1 ELSE 0 END), 0) AS failed_turns,
                    COALESCE(SUM(CASE WHEN status = 'cancelled' THEN 1 ELSE 0 END), 0) AS cancelled_turns,
                    COALESCE(SUM(safe_fallback), 0) AS safe_fallback_turns,
                    COALESCE(AVG(CASE WHEN status != 'started' THEN duration_ms END), 0) AS avg_duration,
                    COALESCE(SUM(tool_call_count), 0) AS tool_calls,
                    COALESCE(SUM(tool_success_count), 0) AS tool_successes,
                    COALESCE(SUM(model_call_count), 0) AS model_calls,
                    COALESCE(SUM(model_failure_count), 0) AS model_failures,
                    COALESCE(SUM(total_tokens), 0) AS total_tokens
                FROM turn_traces
                WHERE user_id = ?
                """,
                (user_id,),
            )
            row = await cursor.fetchone()
        tool_calls = int(row["tool_calls"])
        model_calls = int(row["model_calls"])
        return TraceSummary(
            total_turns=int(row["total_turns"]),
            completed_turns=int(row["completed_turns"]),
            failed_turns=int(row["failed_turns"]),
            cancelled_turns=int(row["cancelled_turns"]),
            safe_fallback_turns=int(row["safe_fallback_turns"]),
            average_duration_ms=round(float(row["avg_duration"]), 2),
            tool_calls=tool_calls,
            tool_success_rate=round(int(row["tool_successes"]) / tool_calls, 4) if tool_calls else 0.0,
            model_calls=model_calls,
            model_failure_rate=round(int(row["model_failures"]) / model_calls, 4) if model_calls else 0.0,
            total_tokens=int(row["total_tokens"]),
        )

    @staticmethod
    def _trace_from_row(row: aiosqlite.Row) -> TurnTrace:
        return TurnTrace(
            id=row["id"],
            request_id=row["request_id"],
            conversation_id=row["conversation_id"],
            user_id=row["user_id"],
            scenario=row["scenario"],
            status=row["status"],
            safe_fallback=bool(row["safe_fallback"]),
            error_code=row["error_code"],
            input_chars=row["input_chars"],
            recent_message_count=row["recent_message_count"],
            summary_used=bool(row["summary_used"]),
            long_term_memory_count=row["long_term_memory_count"],
            tool_call_count=row["tool_call_count"],
            tool_success_count=row["tool_success_count"],
            model_call_count=row["model_call_count"],
            model_failure_count=row["model_failure_count"],
            prompt_tokens=row["prompt_tokens"],
            completion_tokens=row["completion_tokens"],
            total_tokens=row["total_tokens"],
            duration_ms=row["duration_ms"],
            created_at=datetime.fromisoformat(row["created_at"]),
            completed_at=datetime.fromisoformat(row["completed_at"]) if row["completed_at"] else None,
        )

    @staticmethod
    def _tool_span_from_row(row: aiosqlite.Row) -> ToolSpan:
        return ToolSpan(
            id=row["id"],
            name=row["tool_name"],
            status=row["status"],
            error_code=row["error_code"],
            retryable=bool(row["retryable"]),
            latency_ms=row["latency_ms"],
            created_at=datetime.fromisoformat(row["created_at"]),
            completed_at=datetime.fromisoformat(row["completed_at"]) if row["completed_at"] else None,
        )

    @staticmethod
    def _model_span_from_row(row: aiosqlite.Row) -> ModelSpan:
        return ModelSpan(
            id=row["id"],
            provider=row["provider"],
            model=row["model"],
            status=row["status"],
            error_code=row["error_code"],
            prompt_tokens=row["prompt_tokens"],
            completion_tokens=row["completion_tokens"],
            total_tokens=row["total_tokens"],
            latency_ms=row["latency_ms"],
            created_at=datetime.fromisoformat(row["created_at"]),
            completed_at=datetime.fromisoformat(row["completed_at"]) if row["completed_at"] else None,
        )
