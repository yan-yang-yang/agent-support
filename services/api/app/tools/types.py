from __future__ import annotations

from dataclasses import asdict, dataclass
from typing import Any, Literal, TypeAlias

from pydantic import BaseModel, ConfigDict, Field


ToolName: TypeAlias = Literal[
    "get_active_rental",
    "list_recent_orders",
    "get_order_billing",
    "get_station_status",
    "find_nearby_stations",
    "create_support_ticket",
]


class StrictArguments(BaseModel):
    model_config = ConfigDict(extra="forbid")


class GetActiveRentalArguments(StrictArguments):
    pass


class ListRecentOrdersArguments(StrictArguments):
    limit: int = Field(ge=1, le=20)


class GetOrderBillingArguments(StrictArguments):
    order_id: str = Field(min_length=1, max_length=80)


class GetStationStatusArguments(StrictArguments):
    station_id: str = Field(min_length=1, max_length=80)


class FindNearbyStationsArguments(StrictArguments):
    lat: float = Field(ge=-90, le=90)
    lng: float = Field(ge=-180, le=180)
    purpose: Literal["borrow", "return"]
    radius_m: int = Field(ge=100, le=20_000)


class TicketReferences(StrictArguments):
    rental_id: str | None
    order_id: str | None
    station_id: str | None


class CreateSupportTicketArguments(StrictArguments):
    category: Literal["return_failure", "billing_dispute", "other"]
    references: TicketReferences
    summary: str = Field(min_length=1, max_length=1000)
    idempotency_key: str = Field(min_length=8, max_length=120)


TOOL_ARGUMENT_MODELS: dict[str, type[StrictArguments]] = {
    "get_active_rental": GetActiveRentalArguments,
    "list_recent_orders": ListRecentOrdersArguments,
    "get_order_billing": GetOrderBillingArguments,
    "get_station_status": GetStationStatusArguments,
    "find_nearby_stations": FindNearbyStationsArguments,
    "create_support_ticket": CreateSupportTicketArguments,
}


class RentalRecord(BaseModel):
    id: str
    order_id: str
    station_id: str
    started_at: str
    status: str


class OrderRecord(BaseModel):
    id: str
    status: str
    duration_minutes: int
    total_amount: float


class BillingItemRecord(BaseModel):
    code: str
    label: str
    amount: float


class BillingRecord(BaseModel):
    order_id: str
    items: list[BillingItemRecord]
    total_amount: float


class StationRecord(BaseModel):
    id: str
    name: str
    lat: float
    lng: float
    online: bool
    available_umbrellas: int
    available_docks: int
    updated_at: str | None = None
    distance_m: int | None = None


class SupportTicketRecord(BaseModel):
    id: str
    category: str
    status: str
    references: dict[str, str]
    summary: str


@dataclass(frozen=True, slots=True)
class ToolContext:
    user_id: str
    conversation_id: str
    request_id: str
    tool_call_index: int
    max_tool_calls: int


@dataclass(frozen=True, slots=True)
class ToolResult:
    call_id: str
    name: str
    status: Literal["success", "error", "denied"]
    data: Any = None
    error_code: str | None = None
    retryable: bool = False

    def to_state(self) -> dict[str, Any]:
        return asdict(self)
