from __future__ import annotations

import asyncio
import sqlite3

from app.business import BusinessGatewayError
from app.tools.executor import ToolExecutor
from app.tools.repository import ToolCallRepository
from app.tools.types import ToolContext


class RecordingBusinessGateway:
    def __init__(self) -> None:
        self.ticket_payload: dict[str, object] | None = None

    async def get_active_rental(self, user_id: str):
        return {
            "id": "rental-1",
            "order_id": "order-1",
            "station_id": "station-1",
            "started_at": "2026-11-16T08:30:00+08:00",
            "status": "active",
        }

    async def list_recent_orders(self, user_id: str, limit: int = 10):
        return []

    async def get_order_billing(self, order_id: str):
        return {}

    async def get_station_status(self, station_id: str):
        return {}

    async def find_nearby_stations(self, **kwargs):
        return []

    async def create_support_ticket(self, payload: dict[str, object]):
        self.ticket_payload = payload
        return {
            "id": "TKT-1",
            "category": payload["category"],
            "status": "open",
            "references": payload["references"],
            "summary": payload["summary"],
        }


def context(index: int = 0, maximum: int = 6) -> ToolContext:
    return ToolContext(
        user_id="trusted-user",
        conversation_id="conversation-1",
        request_id="request-1",
        tool_call_index=index,
        max_tool_calls=maximum,
    )


def test_allowlisted_tool_executes_and_is_audited(tmp_path) -> None:
    database_path = tmp_path / "tools.db"
    repository = ToolCallRepository(database_path)
    gateway = RecordingBusinessGateway()

    async def exercise():
        await repository.initialize()
        executor = ToolExecutor(gateway=gateway, repository=repository)
        return await executor.execute("get_active_rental", {}, context())

    result = asyncio.run(exercise())

    assert result.status == "success"
    assert result.data["id"] == "rental-1"
    with sqlite3.connect(database_path) as database:
        row = database.execute(
            "SELECT tool_name, status, user_id FROM tool_calls"
        ).fetchone()
    assert row == ("get_active_rental", "success", "trusted-user")


def test_unknown_tool_and_user_override_are_denied(tmp_path) -> None:
    repository = ToolCallRepository(tmp_path / "denied.db")
    gateway = RecordingBusinessGateway()

    async def exercise():
        await repository.initialize()
        executor = ToolExecutor(gateway=gateway, repository=repository)
        unknown = await executor.execute("refund_order", {"order_id": "order-1"}, context())
        override = await executor.execute(
            "get_active_rental",
            {"user_id": "another-user"},
            context(index=1),
        )
        return unknown, override

    unknown, override = asyncio.run(exercise())

    assert unknown.status == "denied"
    assert unknown.error_code == "TOOL_NOT_ALLOWED"
    assert override.status == "denied"
    assert override.error_code == "USER_OVERRIDE_DENIED"


def test_ticket_tool_injects_trusted_user_and_is_idempotency_ready(tmp_path) -> None:
    repository = ToolCallRepository(tmp_path / "ticket.db")
    gateway = RecordingBusinessGateway()

    async def exercise():
        await repository.initialize()
        executor = ToolExecutor(gateway=gateway, repository=repository)
        return await executor.execute(
            "create_support_ticket",
            {
                "category": "billing_dispute",
                "references": {
                    "rental_id": None,
                    "order_id": "order-1",
                    "station_id": None,
                },
                "summary": "计费仍有异议",
                "idempotency_key": "request-1:billing",
            },
            context(),
        )

    result = asyncio.run(exercise())

    assert result.status == "success"
    assert gateway.ticket_payload is not None
    assert gateway.ticket_payload["user_id"] == "trusted-user"
    assert gateway.ticket_payload["idempotency_key"] == "request-1:billing"


def test_retryable_business_failure_never_returns_success(tmp_path) -> None:
    class TimeoutGateway(RecordingBusinessGateway):
        async def get_station_status(self, station_id: str):
            raise BusinessGatewayError(
                "timeout",
                safe_code="BUSINESS_API_TIMEOUT",
                retryable=True,
            )

    repository = ToolCallRepository(tmp_path / "timeout.db")

    async def exercise():
        await repository.initialize()
        executor = ToolExecutor(gateway=TimeoutGateway(), repository=repository)
        return await executor.execute(
            "get_station_status",
            {"station_id": "slow-station"},
            context(),
        )

    result = asyncio.run(exercise())

    assert result.status == "error"
    assert result.data is None
    assert result.retryable is True
    assert result.error_code == "BUSINESS_API_TIMEOUT"
