from __future__ import annotations

import asyncio

import pytest

from app.agent.runner import AgentRunner
from app.tools.executor import ToolExecutor
from app.tools.repository import ToolCallRepository


class ScenarioBusinessGateway:
    def __init__(self) -> None:
        self.created_tickets: dict[str, dict[str, object]] = {}

    async def get_active_rental(self, user_id: str):
        return {
            "id": "rental-active",
            "order_id": "ORDER-2026-001",
            "station_id": "station-full",
            "started_at": "2026-11-16T08:30:00+08:00",
            "status": "active",
        }

    async def list_recent_orders(self, user_id: str, limit: int = 10):
        return [
            {
                "id": "ORDER-2026-001",
                "status": "active",
                "duration_minutes": 42,
                "total_amount": 12.0,
            }
        ][:limit]

    async def get_order_billing(self, order_id: str):
        return {
            "order_id": order_id,
            "items": [
                {"code": "base_fee", "label": "基础使用费", "amount": 8.0},
                {"code": "overtime_fee", "label": "超时费", "amount": 4.0},
            ],
            "total_amount": 12.0,
        }

    async def get_station_status(self, station_id: str):
        return {
            "id": station_id,
            "name": "已满测试网点",
            "lat": 30.2741,
            "lng": 120.1551,
            "online": True,
            "available_umbrellas": 8,
            "available_docks": 0,
            "updated_at": "2026-11-17T09:00:00+08:00",
        }

    async def find_nearby_stations(
        self,
        *,
        lat: float,
        lng: float,
        purpose: str,
        radius_m: int = 3000,
    ):
        return [
            {
                "id": "station-nearby",
                "name": "附近可用网点",
                "lat": 30.2748,
                "lng": 120.1568,
                "online": True,
                "available_umbrellas": 6,
                "available_docks": 4,
                "distance_m": 181,
                "updated_at": "2026-11-17T09:00:00+08:00",
            }
        ]

    async def create_support_ticket(self, payload: dict[str, object]):
        key = str(payload["idempotency_key"])
        if key not in self.created_tickets:
            self.created_tickets[key] = {
                "id": "TKT-AGENT-001",
                "category": payload["category"],
                "status": "open",
                "references": payload["references"],
                "summary": payload["summary"],
            }
        return self.created_tickets[key]


def build_runner(tmp_path, *, max_tool_calls: int = 6):
    repository = ToolCallRepository(tmp_path / "agent.db")
    gateway = ScenarioBusinessGateway()

    async def initialize():
        await repository.initialize()

    asyncio.run(initialize())
    executor = ToolExecutor(gateway=gateway, repository=repository)
    return AgentRunner(executor=executor, max_tool_calls=max_tool_calls), gateway


def run(runner: AgentRunner, text: str, request_id: str = "request-agent-001"):
    return asyncio.run(
        runner.run_turn(
            user_id="demo-user",
            conversation_id="conversation-agent-001",
            request_id=request_id,
            content=text,
        )
    )


@pytest.mark.parametrize(
    ("text", "scenario"),
    [
        ("伞插回去了还在计费", "return_failure"),
        ("为什么扣了我两次钱", "billing_dispute"),
        ("附近哪里能还伞", "nearby_station"),
    ],
)
def test_routes_supported_scenarios(tmp_path, text: str, scenario: str) -> None:
    runner, _ = build_runner(tmp_path)
    result = run(runner, text)
    assert result.scenario == scenario
    assert result.safe_fallback is False


def test_return_failure_uses_safe_read_tools_and_recommends_capacity(tmp_path) -> None:
    runner, _ = build_runner(tmp_path)
    result = run(runner, "伞插不进去")

    assert result.executed_tools == (
        "get_active_rental",
        "get_station_status",
        "get_order_billing",
        "find_nearby_stations",
    )
    assert "结束订单" not in result.executed_tools
    assert result.card is not None
    assert result.card["kind"] == "rental"
    assert "附近可用网点" in result.verified_response


def test_billing_amounts_come_from_tools_and_refund_only_creates_ticket(tmp_path) -> None:
    runner, _ = build_runner(tmp_path)
    result = run(runner, "费用不对，给我退款")

    assert result.card is not None
    assert result.card["total"] == "¥12.00"
    assert "create_support_ticket" in result.executed_tools
    assert "refund" not in result.executed_tools
    assert "没有执行退款" in result.verified_response


def test_nearby_station_returns_sorted_business_inventory(tmp_path) -> None:
    runner, _ = build_runner(tmp_path)
    result = run(runner, "附近哪里可以还伞")

    assert result.executed_tools == ("find_nearby_stations",)
    assert result.card is not None
    assert result.card["stations"][0]["distance"] == "181m"
    assert result.card["stations"][0]["docks"] == 4


def test_unknown_intent_uses_fallback_without_tools(tmp_path) -> None:
    runner, _ = build_runner(tmp_path)
    result = run(runner, "今天天气怎么样")

    assert result.scenario == "unknown"
    assert result.safe_fallback is True
    assert result.executed_tools == ()
    assert "还伞失败、计费疑问和附近网点" in result.verified_response


def test_tool_loop_stops_at_configured_limit(tmp_path) -> None:
    runner, _ = build_runner(tmp_path, max_tool_calls=2)
    result = run(runner, "伞插不进去")

    assert len(result.executed_tools) == 2
    assert result.safe_fallback is True
    assert result.error_code == "TOOL_LOOP_LIMIT"
    assert "安全上限" in result.verified_response
