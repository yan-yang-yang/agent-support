from __future__ import annotations

from datetime import datetime
from typing import Literal

from pydantic import BaseModel, Field


class Rental(BaseModel):
    id: str
    user_id: str
    order_id: str
    umbrella_id: str
    station_id: str
    started_at: datetime
    status: Literal["active", "completed"]


class Order(BaseModel):
    id: str
    user_id: str
    rental_id: str | None = None
    status: Literal["active", "completed", "cancelled"]
    started_at: datetime
    ended_at: datetime | None = None
    duration_minutes: int = Field(ge=0)
    total_amount: float = Field(ge=0)
    currency: str = "CNY"


class BillingItem(BaseModel):
    code: str
    label: str
    amount: float = Field(ge=0)


class Billing(BaseModel):
    order_id: str
    currency: str = "CNY"
    items: list[BillingItem]
    total_amount: float = Field(ge=0)
    rule_version: str


class Station(BaseModel):
    id: str
    name: str
    address: str
    lat: float
    lng: float
    online: bool
    available_umbrellas: int = Field(ge=0)
    available_docks: int = Field(ge=0)
    updated_at: datetime
    distance_m: int | None = Field(default=None, ge=0)


class SupportTicketCreate(BaseModel):
    user_id: str
    category: Literal["return_failure", "billing_dispute", "other"]
    references: dict[str, str] = Field(default_factory=dict)
    summary: str = Field(min_length=1, max_length=1000)
    idempotency_key: str = Field(min_length=8, max_length=120)


class SupportTicket(BaseModel):
    id: str
    user_id: str
    category: Literal["return_failure", "billing_dispute", "other"]
    references: dict[str, str]
    summary: str
    status: Literal["open", "processing", "resolved"]
    created_at: datetime
