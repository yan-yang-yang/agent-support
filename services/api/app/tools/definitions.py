from __future__ import annotations

from ..model_gateway.types import ToolDefinition
from .types import TOOL_ARGUMENT_MODELS


DESCRIPTIONS = {
    "get_active_rental": "查询当前登录用户正在进行的公共雨伞租借。用户身份由服务端注入。",
    "list_recent_orders": "查询当前登录用户最近的公共雨伞订单。用户身份由服务端注入。",
    "get_order_billing": "查询指定订单的业务计费项目和业务系统计算的合计金额。",
    "get_station_status": "查询指定公共雨伞网点的在线状态、雨伞库存和可还空位。",
    "find_nearby_stations": "按位置和借伞或还伞目的查询附近在线网点。",
    "create_support_ticket": "为无法自动解决的问题创建幂等客服工单；不能退款或修改订单。",
}


def _strict_schema(schema: dict[str, object]) -> dict[str, object]:
    result = dict(schema)
    if result.get("type") == "object":
        properties = result.get("properties") or {}
        result["required"] = list(properties)
        result["additionalProperties"] = False
        result["properties"] = {
            key: _strict_schema(value) if isinstance(value, dict) else value
            for key, value in properties.items()
        }
    if isinstance(result.get("$defs"), dict):
        result["$defs"] = {
            key: _strict_schema(value) if isinstance(value, dict) else value
            for key, value in result["$defs"].items()
        }
    for keyword in ("anyOf", "oneOf", "allOf"):
        if isinstance(result.get(keyword), list):
            result[keyword] = [
                _strict_schema(item) if isinstance(item, dict) else item
                for item in result[keyword]
            ]
    return result


TOOL_DEFINITIONS = [
    ToolDefinition(
        name=name,
        description=DESCRIPTIONS[name],
        parameters=_strict_schema(model.model_json_schema()),
        strict=True,
    )
    for name, model in TOOL_ARGUMENT_MODELS.items()
]
