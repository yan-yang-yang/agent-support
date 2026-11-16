from __future__ import annotations

import json

from fastapi.testclient import TestClient

from app.config import Settings
from app.main import create_app


class FakeBusinessGateway:
    async def get_active_rental(self, user_id: str) -> dict[str, object] | None:
        return {
            "id": "rental-test",
            "user_id": user_id,
            "order_id": "ORDER-TEST",
            "station_id": "station-full",
            "started_at": "2026-11-16T08:30:00+08:00",
        }

    async def list_recent_orders(self, user_id: str, limit: int = 10) -> list[dict[str, object]]:
        return [
            {
                "id": "ORDER-TEST",
                "user_id": user_id,
                "duration_minutes": 42,
            }
        ][:limit]

    async def get_order_billing(self, order_id: str) -> dict[str, object]:
        return {
            "order_id": order_id,
            "items": [
                {"code": "base_fee", "amount": 2.0},
                {"code": "overtime_fee", "amount": 1.0},
            ],
            "total_amount": 3.0,
        }

    async def get_station_status(self, station_id: str) -> dict[str, object]:
        return {
            "id": station_id,
            "name": "测试满桩网点",
            "lat": 30.2741,
            "lng": 120.1551,
            "online": True,
            "available_docks": 0,
        }

    async def find_nearby_stations(
        self,
        *,
        lat: float,
        lng: float,
        purpose: str,
        radius_m: int = 3000,
    ) -> list[dict[str, object]]:
        return [
            {
                "id": "station-nearby",
                "name": "测试可还网点",
                "distance_m": 180,
                "available_umbrellas": 6,
                "available_docks": 4,
            }
        ]

    async def create_support_ticket(self, payload: dict[str, object]) -> dict[str, object]:
        return {"id": "TKT-TEST", "status": "open", **payload}


def parse_sse(text: str) -> list[tuple[str, dict[str, object]]]:
    events: list[tuple[str, dict[str, object]]] = []
    for block in text.strip().split("\n\n"):
        lines = block.splitlines()
        event = next(line.removeprefix("event: ") for line in lines if line.startswith("event: "))
        data = json.loads(next(line.removeprefix("data: ") for line in lines if line.startswith("data: ")))
        events.append((event, data))
    return events


def test_conversation_history_and_sse_persist_messages(tmp_path) -> None:
    app = create_app(
        Settings(database_path=tmp_path / "test.db", stream_character_delay=0),
        business_gateway=FakeBusinessGateway(),
    )
    with TestClient(app) as client:
        created = client.post("/api/v1/conversations", json={}).json()
        conversation_id = created["id"]

        with client.stream(
            "POST",
            f"/api/v1/conversations/{conversation_id}/messages:stream",
            json={"content": "雨伞已经插回去了，为什么还在计费？", "request_id": "request-001"},
        ) as response:
            assert response.status_code == 200
            events = parse_sse(response.read().decode())

        event_names = [event for event, _ in events]
        assert event_names[0] == "message.started"
        assert "assistant.delta" in event_names
        assert "business_card" in event_names
        assert event_names[-1] == "assistant.completed"

        messages = client.get(f"/api/v1/conversations/{conversation_id}/messages").json()
        assert [message["role"] for message in messages] == ["user", "assistant"]
        assert messages[1]["card"]["kind"] == "rental"
        assert messages[1]["card"]["station"] == "测试满桩网点"

        conversations = client.get("/api/v1/conversations").json()
        assert conversations[0]["id"] == conversation_id
        assert conversations[0]["message_count"] == 2
        assert conversations[0]["title"].startswith("雨伞已经插回去了")


def test_conversations_are_scoped_by_demo_user(tmp_path) -> None:
    app = create_app(
        Settings(database_path=tmp_path / "test.db", stream_character_delay=0),
        business_gateway=FakeBusinessGateway(),
    )
    with TestClient(app) as client:
        created = client.post("/api/v1/conversations", json={}, headers={"X-Demo-User": "user-a"}).json()
        response = client.get(
            f"/api/v1/conversations/{created['id']}/messages",
            headers={"X-Demo-User": "user-b"},
        )
        assert response.status_code == 404
