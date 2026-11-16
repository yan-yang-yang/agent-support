from __future__ import annotations

from fastapi.testclient import TestClient


def test_routes_require_internal_token(client: TestClient) -> None:
    response = client.get("/v1/stations/station-tech-a", headers={"X-Internal-Token": "wrong"})
    assert response.status_code == 401


def test_return_user_has_active_rental_with_full_online_station(client: TestClient) -> None:
    rental_response = client.get("/v1/users/demo-return-user/active-rental")
    assert rental_response.status_code == 200
    rental = rental_response.json()

    station_response = client.get(f"/v1/stations/{rental['station_id']}")
    assert station_response.status_code == 200
    station = station_response.json()

    assert rental["status"] == "active"
    assert station["online"] is True
    assert station["available_docks"] == 0


def test_billing_user_has_explainable_line_items(client: TestClient) -> None:
    orders = client.get("/v1/users/demo-billing-user/orders").json()
    assert len(orders) == 1

    billing = client.get(f"/v1/orders/{orders[0]['id']}/billing").json()
    assert billing["total_amount"] == sum(item["amount"] for item in billing["items"])
    assert {item["code"] for item in billing["items"]} == {"base_fee", "overtime_fee"}


def test_nearby_search_filters_and_sorts_return_capacity(client: TestClient) -> None:
    stations = client.get(
        "/v1/stations/nearby",
        params={"lat": 30.2741, "lng": 120.1551, "purpose": "return"},
    ).json()

    assert [station["id"] for station in stations] == ["station-tech-b", "station-south-gate"]
    assert all(station["online"] for station in stations)
    assert all(station["available_docks"] > 0 for station in stations)
    assert [station["distance_m"] for station in stations] == sorted(
        station["distance_m"] for station in stations
    )


def test_ticket_creation_is_idempotent_and_queryable(client: TestClient) -> None:
    payload = {
        "user_id": "demo-return-user",
        "category": "return_failure",
        "references": {"rental_id": "rental-return-active"},
        "summary": "网点已满，用户仍无法还伞",
        "idempotency_key": "conversation-001:return-failure",
    }

    first = client.post("/v1/support-tickets", json=payload)
    second = client.post("/v1/support-tickets", json=payload)

    assert first.status_code == 201
    assert second.status_code == 201
    assert first.json() == second.json()
    assert first.json()["status"] == "open"
    assert client.get(f"/v1/support-tickets/{first.json()['id']}").json() == first.json()


def test_unknown_records_return_404(client: TestClient) -> None:
    assert client.get("/v1/users/unknown/active-rental").status_code == 404
    assert client.get("/v1/orders/unknown/billing").status_code == 404
    assert client.get("/v1/stations/unknown").status_code == 404
