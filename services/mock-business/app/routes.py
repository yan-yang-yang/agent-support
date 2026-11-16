from __future__ import annotations

import secrets
from typing import Literal

from fastapi import APIRouter, Depends, Header, HTTPException, Query, Request, status

from .models import Billing, Order, Rental, Station, SupportTicket, SupportTicketCreate
from .store import BusinessRecordNotFoundError, SeedStore


router = APIRouter(prefix="/v1")


def get_store(request: Request) -> SeedStore:
    return request.app.state.store


def require_internal_token(
    request: Request,
    x_internal_token: str | None = Header(default=None),
) -> None:
    expected_token: str = request.app.state.internal_token
    if x_internal_token is None or not secrets.compare_digest(x_internal_token, expected_token):
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid internal token")


def not_found(error: BusinessRecordNotFoundError) -> HTTPException:
    return HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(error))


@router.get(
    "/users/{user_id}/active-rental",
    response_model=Rental,
    dependencies=[Depends(require_internal_token)],
)
def get_active_rental(user_id: str, store: SeedStore = Depends(get_store)) -> Rental:
    try:
        return store.get_active_rental(user_id)
    except BusinessRecordNotFoundError as error:
        raise not_found(error) from error


@router.get(
    "/users/{user_id}/orders",
    response_model=list[Order],
    dependencies=[Depends(require_internal_token)],
)
def list_orders(
    user_id: str,
    limit: int = Query(default=10, ge=1, le=50),
    store: SeedStore = Depends(get_store),
) -> list[Order]:
    try:
        return store.list_orders(user_id, limit)
    except BusinessRecordNotFoundError as error:
        raise not_found(error) from error


@router.get(
    "/orders/{order_id}/billing",
    response_model=Billing,
    dependencies=[Depends(require_internal_token)],
)
def get_billing(order_id: str, store: SeedStore = Depends(get_store)) -> Billing:
    try:
        return store.get_billing(order_id)
    except BusinessRecordNotFoundError as error:
        raise not_found(error) from error


@router.get(
    "/stations/nearby",
    response_model=list[Station],
    dependencies=[Depends(require_internal_token)],
)
def find_nearby_stations(
    lat: float = Query(ge=-90, le=90),
    lng: float = Query(ge=-180, le=180),
    purpose: Literal["borrow", "return"] = "return",
    radius_m: int = Query(default=3000, alias="radius", ge=100, le=20_000),
    store: SeedStore = Depends(get_store),
) -> list[Station]:
    return store.find_nearby_stations(
        lat=lat,
        lng=lng,
        purpose=purpose,
        radius_m=radius_m,
    )


@router.get(
    "/stations/{station_id}",
    response_model=Station,
    dependencies=[Depends(require_internal_token)],
)
def get_station(station_id: str, store: SeedStore = Depends(get_store)) -> Station:
    try:
        return store.get_station(station_id)
    except BusinessRecordNotFoundError as error:
        raise not_found(error) from error


@router.post(
    "/support-tickets",
    response_model=SupportTicket,
    status_code=status.HTTP_201_CREATED,
    dependencies=[Depends(require_internal_token)],
)
def create_support_ticket(
    payload: SupportTicketCreate,
    store: SeedStore = Depends(get_store),
) -> SupportTicket:
    try:
        return store.create_ticket(payload)
    except BusinessRecordNotFoundError as error:
        raise not_found(error) from error


@router.get(
    "/support-tickets/{ticket_id}",
    response_model=SupportTicket,
    dependencies=[Depends(require_internal_token)],
)
def get_support_ticket(ticket_id: str, store: SeedStore = Depends(get_store)) -> SupportTicket:
    try:
        return store.get_ticket(ticket_id)
    except BusinessRecordNotFoundError as error:
        raise not_found(error) from error
