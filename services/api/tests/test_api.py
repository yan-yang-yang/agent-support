from __future__ import annotations

import json
import sqlite3

from fastapi.testclient import TestClient

from app.config import Settings
from app.main import create_app
from app.model_gateway.protocol import ModelGatewayError
from app.model_gateway.types import VERIFIED_RESPONSE_MARKER, ModelRequest, TextDelta


class FakeBusinessGateway:
    async def get_active_rental(self, user_id: str) -> dict[str, object] | None:
        return {
            "id": "rental-test",
            "user_id": user_id,
            "order_id": "ORDER-TEST",
            "station_id": "station-full",
            "started_at": "2026-11-16T08:30:00+08:00",
            "status": "active",
        }

    async def list_recent_orders(self, user_id: str, limit: int = 10) -> list[dict[str, object]]:
        return [
            {
                "id": "ORDER-TEST",
                "user_id": user_id,
                "status": "active",
                "duration_minutes": 42,
                "total_amount": 3.0,
            }
        ][:limit]

    async def get_order_billing(self, order_id: str) -> dict[str, object]:
        return {
            "order_id": order_id,
            "items": [
                {"code": "base_fee", "label": "基础使用费", "amount": 2.0},
                {"code": "overtime_fee", "label": "超时费", "amount": 1.0},
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
            "available_umbrellas": 8,
            "available_docks": 0,
            "updated_at": "2026-11-16T10:00:00+08:00",
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
                "lat": 30.2748,
                "lng": 120.1568,
                "online": True,
                "distance_m": 180,
                "available_umbrellas": 6,
                "available_docks": 4,
                "updated_at": "2026-11-16T10:00:00+08:00",
            }
        ]

    async def create_support_ticket(self, payload: dict[str, object]) -> dict[str, object]:
        return {
            "id": "TKT-TEST",
            "status": "open",
            "category": payload["category"],
            "references": payload["references"],
            "summary": payload["summary"],
        }


class FailingModelGateway:
    provider_name = "failing-test"
    model_name = "failing-model"

    async def close(self) -> None:
        return None

    async def stream_chat(self, request):
        if False:
            yield None
        raise ModelGatewayError(
            "provider unavailable",
            safe_code="PROVIDER_UNAVAILABLE",
            retryable=True,
        )

    async def complete_structured(self, request, schema):
        raise ModelGatewayError(
            "provider unavailable",
            safe_code="PROVIDER_UNAVAILABLE",
            retryable=True,
        )


class CapturingModelGateway:
    provider_name = "capturing-test"
    model_name = "capturing-model"

    def __init__(self) -> None:
        self.requests: list[ModelRequest] = []

    async def close(self) -> None:
        return None

    async def stream_chat(self, request: ModelRequest):
        self.requests.append(request)
        content = request.messages[-1].content or ""
        response = content.split(VERIFIED_RESPONSE_MARKER, 1)[-1].strip()
        yield TextDelta(response)

    async def complete_structured(self, request, schema):
        raise NotImplementedError


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

    with sqlite3.connect(tmp_path / "test.db") as database:
        model_call = database.execute(
            "SELECT provider, model, status, request_id FROM model_calls"
        ).fetchone()
    assert model_call == ("fake", "fake-support-v1", "completed", "request-001")


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


def test_model_failure_falls_back_to_verified_business_response(tmp_path) -> None:
    app = create_app(
        Settings(database_path=tmp_path / "fallback.db", stream_character_delay=0),
        business_gateway=FakeBusinessGateway(),
        model_gateway=FailingModelGateway(),
    )
    with TestClient(app) as client:
        conversation_id = client.post("/api/v1/conversations", json={}).json()["id"]
        response = client.post(
            f"/api/v1/conversations/{conversation_id}/messages:stream",
            json={"content": "我对订单费用有疑问", "request_id": "request-fallback-001"},
        )

        assert response.status_code == 200
        events = parse_sse(response.text)
        completed = next(data for event, data in events if event == "assistant.completed")
        assert "ORDER-TEST" in completed["message"]["content"]
        assert completed["message"]["card"]["kind"] == "billing"


def test_long_term_memory_is_shared_across_user_conversations_and_can_be_cleared(tmp_path) -> None:
    gateway = CapturingModelGateway()
    app = create_app(
        Settings(database_path=tmp_path / "memory-api.db", stream_character_delay=0),
        business_gateway=FakeBusinessGateway(),
        model_gateway=gateway,
    )
    headers = {"X-Demo-User": "memory-user"}
    with TestClient(app) as client:
        first = client.post("/api/v1/conversations", json={}, headers=headers).json()
        response = client.post(
            f"/api/v1/conversations/{first['id']}/messages:stream",
            json={
                "content": "以后叫我小杨，我的常用网点是软件园 A 口站，回复简短一点",
                "request_id": "memory-request-001",
            },
            headers=headers,
        )
        assert response.status_code == 200

        memories = client.get("/api/v1/memories", headers=headers).json()
        assert {item["key"]: item["value"] for item in memories} == {
            "preferred_name": "小杨",
            "frequent_station": "软件园 A 口站",
            "response_style": "简洁",
        }
        assert client.get(
            "/api/v1/memories",
            headers={"X-Demo-User": "another-user"},
        ).json() == []

        second = client.post("/api/v1/conversations", json={}, headers=headers).json()
        response = client.post(
            f"/api/v1/conversations/{second['id']}/messages:stream",
            json={"content": "附近哪里可以还伞？", "request_id": "memory-request-002"},
            headers=headers,
        )
        events = parse_sse(response.text)
        completed = next(data for event, data in events if event == "assistant.completed")
        assert completed["message"]["content"].startswith("小杨，")
        assert "软件园 A 口站" in (gateway.requests[-1].messages[1].content or "")

        deleted = client.delete("/api/v1/memories", headers=headers).json()
        assert deleted == {"deleted": 3}
        assert client.get("/api/v1/memories", headers=headers).json() == []


def test_model_receives_bounded_recent_context_plus_rolling_summary(tmp_path) -> None:
    gateway = CapturingModelGateway()
    app = create_app(
        Settings(
            database_path=tmp_path / "context-api.db",
            stream_character_delay=0,
            memory_recent_message_limit=2,
            memory_summary_max_chars=500,
        ),
        business_gateway=FakeBusinessGateway(),
        model_gateway=gateway,
    )
    with TestClient(app) as client:
        conversation = client.post("/api/v1/conversations", json={}).json()
        for index, content in enumerate(
            ("第一次咨询的其他问题", "第二次咨询的其他问题", "第三次咨询的其他问题"),
            start=1,
        ):
            response = client.post(
                f"/api/v1/conversations/{conversation['id']}/messages:stream",
                json={"content": content, "request_id": f"context-request-00{index}"},
            )
            assert response.status_code == 200

        final_request = gateway.requests[-1]
        assert len(final_request.messages) == 5
        assert "第一次咨询的其他问题" in (final_request.messages[1].content or "")
        assert final_request.messages[2].content == "第二次咨询的其他问题"
        assert "第三次咨询的其他问题" in (final_request.messages[-1].content or "")

        full_history = client.get(
            f"/api/v1/conversations/{conversation['id']}/messages"
        ).json()
        assert len(full_history) == 6
        assert [message["role"] for message in full_history] == [
            "user",
            "assistant",
            "user",
            "assistant",
            "user",
            "assistant",
        ]


def test_observability_trace_correlates_agent_tools_model_and_tokens(tmp_path) -> None:
    app = create_app(
        Settings(database_path=tmp_path / "trace-api.db", stream_character_delay=0),
        business_gateway=FakeBusinessGateway(),
    )
    headers = {"X-Demo-User": "trace-user"}
    with TestClient(app) as client:
        conversation = client.post("/api/v1/conversations", json={}, headers=headers).json()
        response = client.post(
            f"/api/v1/conversations/{conversation['id']}/messages:stream",
            json={
                "content": "我对最近订单的费用有疑问",
                "request_id": "trace-request-001",
            },
            headers=headers,
        )
        assert response.status_code == 200
        events = parse_sse(response.text)
        started = next(data for event, data in events if event == "message.started")

        traces = client.get("/api/v1/observability/traces", headers=headers).json()
        assert len(traces) == 1
        trace = traces[0]
        assert trace["id"] == started["traceId"]
        assert trace["status"] == "completed"
        assert trace["scenario"] == "billing_dispute"
        assert trace["tool_call_count"] == 2
        assert trace["tool_success_count"] == 2
        assert trace["model_call_count"] == 1
        assert trace["model_failure_count"] == 0
        assert trace["total_tokens"] > 0
        assert trace["duration_ms"] is not None

        detail = client.get(
            f"/api/v1/observability/traces/{trace['id']}",
            headers=headers,
        ).json()
        assert [span["name"] for span in detail["tool_spans"]] == [
            "list_recent_orders",
            "get_order_billing",
        ]
        assert detail["model_spans"][0]["provider"] == "fake"
        assert detail["model_spans"][0]["status"] == "completed"

        unknown_response = client.post(
            f"/api/v1/conversations/{conversation['id']}/messages:stream",
            json={"content": "今天天气怎么样？", "request_id": "trace-request-002"},
            headers=headers,
        )
        assert unknown_response.status_code == 200
        latest_trace = client.get(
            "/api/v1/observability/traces?limit=1",
            headers=headers,
        ).json()[0]
        assert latest_trace["scenario"] == "unknown"
        assert latest_trace["safe_fallback"] is True
        assert latest_trace["tool_call_count"] == 0

        summary = client.get("/api/v1/observability/summary", headers=headers).json()
        assert summary["total_turns"] == 2
        assert summary["completed_turns"] == 2
        assert summary["safe_fallback_turns"] == 1
        assert summary["tool_success_rate"] == 1.0
        assert summary["model_failure_rate"] == 0.0
        assert summary["total_tokens"] > trace["total_tokens"]

        assert client.get(
            "/api/v1/observability/traces",
            headers={"X-Demo-User": "other-user"},
        ).json() == []
        assert client.get(
            f"/api/v1/observability/traces/{trace['id']}",
            headers={"X-Demo-User": "other-user"},
        ).status_code == 404
