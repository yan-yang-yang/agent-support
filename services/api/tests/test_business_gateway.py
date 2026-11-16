from __future__ import annotations

import asyncio

import httpx

from app.business import HttpUmbrellaBusinessGateway


def test_http_business_gateway_maps_paths_auth_and_payloads() -> None:
    requests: list[httpx.Request] = []

    def handler(request: httpx.Request) -> httpx.Response:
        requests.append(request)
        assert request.headers["X-Internal-Token"] == "test-token"
        if request.url.path.endswith("/active-rental"):
            return httpx.Response(
                200,
                json={"id": "rental-1", "order_id": "order-1", "station_id": "station-1"},
            )
        if request.url.path == "/v1/stations/nearby":
            return httpx.Response(
                200,
                json=[
                    {
                        "id": "station-2",
                        "distance_m": 180,
                        "available_docks": 4,
                    }
                ],
            )
        raise AssertionError(f"Unexpected request: {request.method} {request.url}")

    async def exercise_gateway() -> None:
        gateway = HttpUmbrellaBusinessGateway(
            base_url="http://business.test",
            internal_token="test-token",
            timeout_seconds=1,
            transport=httpx.MockTransport(handler),
        )
        try:
            rental = await gateway.get_active_rental("demo-user")
            stations = await gateway.find_nearby_stations(
                lat=30.2741,
                lng=120.1551,
                purpose="return",
            )
        finally:
            await gateway.close()

        assert rental is not None
        assert rental["order_id"] == "order-1"
        assert stations[0]["available_docks"] == 4

    asyncio.run(exercise_gateway())

    assert [request.url.path for request in requests] == [
        "/v1/users/demo-user/active-rental",
        "/v1/stations/nearby",
    ]
    assert requests[1].url.params["purpose"] == "return"
    assert requests[1].url.params["radius"] == "3000"
