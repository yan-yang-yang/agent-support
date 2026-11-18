from __future__ import annotations

import json
import math
import re
from copy import deepcopy
from datetime import UTC, datetime
from pathlib import Path
from uuid import NAMESPACE_URL, uuid5

from .models import Billing, Order, Rental, Station, SupportTicket, SupportTicketCreate


class BusinessRecordNotFoundError(LookupError):
    pass


class SeedStore:
    def __init__(self, seed_path: Path) -> None:
        seed = json.loads(seed_path.read_text(encoding="utf-8"))
        self._users: dict[str, dict[str, object]] = seed["users"]
        self._rentals: dict[str, dict[str, object]] = {
            item["id"]: item for item in seed["rentals"]
        }
        self._orders: dict[str, dict[str, object]] = {
            item["id"]: item for item in seed["orders"]
        }
        self._billing: dict[str, dict[str, object]] = {
            item["order_id"]: item for item in seed["billing"]
        }
        self._stations: dict[str, dict[str, object]] = {
            item["id"]: item for item in seed["stations"]
        }
        self._tickets_by_id: dict[str, SupportTicket] = {}
        self._ticket_ids_by_key: dict[str, str] = {}

    @classmethod
    def from_default_seed(cls) -> "SeedStore":
        return cls(Path(__file__).with_name("seed.json"))

    def get_active_rental(self, user_id: str) -> Rental:
        template_user_id = self._resolve_user_id(user_id)
        user = self._users[template_user_id]
        rental_id = user.get("active_rental_id")
        if not rental_id or rental_id not in self._rentals:
            raise BusinessRecordNotFoundError(f"No active rental for {user_id}")
        rental = Rental.model_validate(deepcopy(self._rentals[str(rental_id)]))
        return rental.model_copy(update={"user_id": user_id})

    def list_orders(self, user_id: str, limit: int) -> list[Order]:
        template_user_id = self._resolve_user_id(user_id)
        orders = [
            Order.model_validate(deepcopy(order)).model_copy(update={"user_id": user_id})
            for order in self._orders.values()
            if order["user_id"] == template_user_id
        ]
        orders.sort(key=lambda order: order.started_at, reverse=True)
        return orders[:limit]

    def get_billing(self, order_id: str) -> Billing:
        billing = self._billing.get(order_id)
        if billing is None:
            raise BusinessRecordNotFoundError(f"Billing not found: {order_id}")
        return Billing.model_validate(deepcopy(billing))

    def get_station(self, station_id: str) -> Station:
        station = self._stations.get(station_id)
        if station is None:
            raise BusinessRecordNotFoundError(f"Station not found: {station_id}")
        return Station.model_validate(deepcopy(station))

    def find_nearby_stations(
        self,
        *,
        lat: float,
        lng: float,
        purpose: str,
        radius_m: int,
    ) -> list[Station]:
        matches: list[Station] = []
        for raw_station in self._stations.values():
            station = Station.model_validate(deepcopy(raw_station))
            distance = round(self._distance_m(lat, lng, station.lat, station.lng))
            has_capacity = (
                station.available_docks > 0
                if purpose == "return"
                else station.available_umbrellas > 0
            )
            if station.online and has_capacity and distance <= radius_m:
                matches.append(station.model_copy(update={"distance_m": distance}))
        return sorted(matches, key=lambda station: station.distance_m or 0)

    def create_ticket(self, payload: SupportTicketCreate) -> SupportTicket:
        self._require_user(payload.user_id)
        existing_id = self._ticket_ids_by_key.get(payload.idempotency_key)
        if existing_id:
            return self._tickets_by_id[existing_id].model_copy(deep=True)

        stable_id = f"TKT-{uuid5(NAMESPACE_URL, payload.idempotency_key).hex[:12].upper()}"
        ticket = SupportTicket(
            id=stable_id,
            user_id=payload.user_id,
            category=payload.category,
            references=deepcopy(payload.references),
            summary=payload.summary,
            status="open",
            created_at=datetime.now(UTC),
        )
        self._tickets_by_id[ticket.id] = ticket
        self._ticket_ids_by_key[payload.idempotency_key] = ticket.id
        return ticket.model_copy(deep=True)

    def get_ticket(self, ticket_id: str) -> SupportTicket:
        ticket = self._tickets_by_id.get(ticket_id)
        if ticket is None:
            raise BusinessRecordNotFoundError(f"Ticket not found: {ticket_id}")
        return ticket.model_copy(deep=True)

    def _require_user(self, user_id: str) -> dict[str, object]:
        return self._users[self._resolve_user_id(user_id)]

    def _resolve_user_id(self, user_id: str) -> str:
        if user_id in self._users:
            return user_id
        template_user_id, separator, client_id = user_id.partition("~")
        if (
            separator
            and template_user_id in self._users
            and re.fullmatch(r"[A-Za-z0-9_-]{8,80}", client_id)
        ):
            return template_user_id
        raise BusinessRecordNotFoundError(f"User not found: {user_id}")

    @staticmethod
    def _distance_m(lat1: float, lng1: float, lat2: float, lng2: float) -> float:
        radius = 6_371_000
        phi1 = math.radians(lat1)
        phi2 = math.radians(lat2)
        delta_phi = math.radians(lat2 - lat1)
        delta_lambda = math.radians(lng2 - lng1)
        value = (
            math.sin(delta_phi / 2) ** 2
            + math.cos(phi1) * math.cos(phi2) * math.sin(delta_lambda / 2) ** 2
        )
        return radius * 2 * math.atan2(math.sqrt(value), math.sqrt(1 - value))
