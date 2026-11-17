from __future__ import annotations

from typing import Any, Protocol

import httpx


BusinessRecord = dict[str, Any]


class BusinessGateway(Protocol):
    async def get_active_rental(self, user_id: str) -> BusinessRecord | None: ...

    async def list_recent_orders(self, user_id: str, limit: int = 10) -> list[BusinessRecord]: ...

    async def get_order_billing(self, order_id: str) -> BusinessRecord: ...

    async def get_station_status(self, station_id: str) -> BusinessRecord: ...

    async def find_nearby_stations(
        self,
        *,
        lat: float,
        lng: float,
        purpose: str,
        radius_m: int = 3000,
    ) -> list[BusinessRecord]: ...

    async def create_support_ticket(self, payload: BusinessRecord) -> BusinessRecord: ...


class BusinessGatewayError(RuntimeError):
    def __init__(
        self,
        message: str,
        *,
        safe_code: str = "BUSINESS_API_ERROR",
        retryable: bool = False,
    ) -> None:
        super().__init__(message)
        self.safe_code = safe_code
        self.retryable = retryable


class HttpUmbrellaBusinessGateway:
    def __init__(
        self,
        *,
        base_url: str,
        internal_token: str,
        timeout_seconds: float,
        transport: httpx.AsyncBaseTransport | None = None,
    ) -> None:
        self._client = httpx.AsyncClient(
            base_url=base_url.rstrip("/"),
            headers={"X-Internal-Token": internal_token},
            timeout=timeout_seconds,
            transport=transport,
        )

    async def close(self) -> None:
        await self._client.aclose()

    async def get_active_rental(self, user_id: str) -> BusinessRecord | None:
        response = await self._request("GET", f"/v1/users/{user_id}/active-rental")
        if response.status_code == 404:
            return None
        return self._json(response)

    async def list_recent_orders(self, user_id: str, limit: int = 10) -> list[BusinessRecord]:
        response = await self._request(
            "GET",
            f"/v1/users/{user_id}/orders",
            params={"limit": limit},
        )
        if response.status_code == 404:
            return []
        payload = self._json(response)
        if not isinstance(payload, list):
            raise BusinessGatewayError("Business API returned an invalid orders payload")
        return payload

    async def get_order_billing(self, order_id: str) -> BusinessRecord:
        return self._json(await self._request("GET", f"/v1/orders/{order_id}/billing"))

    async def get_station_status(self, station_id: str) -> BusinessRecord:
        return self._json(await self._request("GET", f"/v1/stations/{station_id}"))

    async def find_nearby_stations(
        self,
        *,
        lat: float,
        lng: float,
        purpose: str,
        radius_m: int = 3000,
    ) -> list[BusinessRecord]:
        response = await self._request(
            "GET",
            "/v1/stations/nearby",
            params={
                "lat": lat,
                "lng": lng,
                "purpose": purpose,
                "radius": radius_m,
            },
        )
        payload = self._json(response)
        if not isinstance(payload, list):
            raise BusinessGatewayError("Business API returned an invalid stations payload")
        return payload

    async def create_support_ticket(self, payload: BusinessRecord) -> BusinessRecord:
        return self._json(await self._request("POST", "/v1/support-tickets", json=payload))

    async def _request(self, method: str, path: str, **kwargs: Any) -> httpx.Response:
        try:
            return await self._client.request(method, path, **kwargs)
        except httpx.TimeoutException as error:
            raise BusinessGatewayError(
                "Business API timeout",
                safe_code="BUSINESS_API_TIMEOUT",
                retryable=True,
            ) from error
        except httpx.RequestError as error:
            raise BusinessGatewayError(
                "Business API unavailable",
                safe_code="BUSINESS_API_UNAVAILABLE",
                retryable=True,
            ) from error

    @staticmethod
    def _json(response: httpx.Response) -> Any:
        try:
            response.raise_for_status()
        except httpx.HTTPStatusError as error:
            retryable = response.status_code >= 500 or response.status_code in {408, 429}
            raise BusinessGatewayError(
                f"Business API request failed with status {response.status_code}",
                safe_code=("BUSINESS_API_UNAVAILABLE" if retryable else "BUSINESS_API_REJECTED"),
                retryable=retryable,
            ) from error
        try:
            return response.json()
        except ValueError as error:
            raise BusinessGatewayError(
                "Business API returned invalid JSON",
                safe_code="BUSINESS_API_INVALID_RESPONSE",
            ) from error
