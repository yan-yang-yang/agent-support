from __future__ import annotations

from typing import Any

from ..business import BusinessGateway, BusinessGatewayError
from .repository import ToolCallRepository
from .risk_policy import ToolPolicyError, ToolRiskPolicy
from .types import (
    BillingRecord,
    CreateSupportTicketArguments,
    FindNearbyStationsArguments,
    GetOrderBillingArguments,
    GetStationStatusArguments,
    ListRecentOrdersArguments,
    OrderRecord,
    RentalRecord,
    StationRecord,
    SupportTicketRecord,
    ToolContext,
    ToolResult,
)


class ToolExecutor:
    def __init__(
        self,
        *,
        gateway: BusinessGateway,
        repository: ToolCallRepository,
        risk_policy: ToolRiskPolicy | None = None,
    ) -> None:
        self._gateway = gateway
        self._repository = repository
        self._risk_policy = risk_policy or ToolRiskPolicy()

    async def execute(
        self,
        name: str,
        arguments: dict[str, object],
        context: ToolContext,
    ) -> ToolResult:
        call_id = await self._repository.start(
            request_id=context.request_id,
            conversation_id=context.conversation_id,
            user_id=context.user_id,
            tool_name=name,
            arguments=arguments,
        )
        try:
            validated = self._risk_policy.validate(name, arguments, context)
            data = await self._dispatch(name, validated, context)
            await self._repository.complete(call_id, status="success", result=data)
            return ToolResult(call_id=call_id, name=name, status="success", data=data)
        except ToolPolicyError as error:
            await self._repository.complete(
                call_id,
                status="denied",
                error_code=error.safe_code,
            )
            return ToolResult(
                call_id=call_id,
                name=name,
                status="denied",
                error_code=error.safe_code,
            )
        except BusinessGatewayError as error:
            await self._repository.complete(
                call_id,
                status="error",
                error_code=error.safe_code,
                retryable=error.retryable,
            )
            return ToolResult(
                call_id=call_id,
                name=name,
                status="error",
                error_code=error.safe_code,
                retryable=error.retryable,
            )
        except Exception:
            await self._repository.complete(
                call_id,
                status="error",
                error_code="TOOL_EXECUTION_ERROR",
            )
            return ToolResult(
                call_id=call_id,
                name=name,
                status="error",
                error_code="TOOL_EXECUTION_ERROR",
            )

    async def _dispatch(
        self,
        name: str,
        arguments: Any,
        context: ToolContext,
    ) -> Any:
        if name == "get_active_rental":
            rental = await self._gateway.get_active_rental(context.user_id)
            return RentalRecord.model_validate(rental).model_dump(mode="json") if rental else None

        if name == "list_recent_orders":
            assert isinstance(arguments, ListRecentOrdersArguments)
            orders = await self._gateway.list_recent_orders(context.user_id, arguments.limit)
            return [OrderRecord.model_validate(order).model_dump(mode="json") for order in orders]

        if name == "get_order_billing":
            assert isinstance(arguments, GetOrderBillingArguments)
            billing = await self._gateway.get_order_billing(arguments.order_id)
            return BillingRecord.model_validate(billing).model_dump(mode="json")

        if name == "get_station_status":
            assert isinstance(arguments, GetStationStatusArguments)
            station = await self._gateway.get_station_status(arguments.station_id)
            return StationRecord.model_validate(station).model_dump(mode="json")

        if name == "find_nearby_stations":
            assert isinstance(arguments, FindNearbyStationsArguments)
            stations = await self._gateway.find_nearby_stations(
                lat=arguments.lat,
                lng=arguments.lng,
                purpose=arguments.purpose,
                radius_m=arguments.radius_m,
            )
            return [StationRecord.model_validate(station).model_dump(mode="json") for station in stations]

        if name == "create_support_ticket":
            assert isinstance(arguments, CreateSupportTicketArguments)
            payload = arguments.model_dump(mode="json")
            payload["references"] = {
                key: value
                for key, value in payload["references"].items()
                if value is not None
            }
            payload["user_id"] = context.user_id
            ticket = await self._gateway.create_support_ticket(payload)
            return SupportTicketRecord.model_validate(ticket).model_dump(mode="json")

        raise ToolPolicyError("Tool is not allowlisted", safe_code="TOOL_NOT_ALLOWED")
