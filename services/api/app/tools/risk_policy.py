from __future__ import annotations

from pydantic import ValidationError

from .types import TOOL_ARGUMENT_MODELS, StrictArguments, ToolContext


class ToolPolicyError(ValueError):
    def __init__(self, message: str, *, safe_code: str) -> None:
        super().__init__(message)
        self.safe_code = safe_code


class ToolRiskPolicy:
    def validate(
        self,
        name: str,
        arguments: dict[str, object],
        context: ToolContext,
    ) -> StrictArguments:
        if context.tool_call_index >= context.max_tool_calls:
            raise ToolPolicyError("Tool call limit reached", safe_code="TOOL_LIMIT_REACHED")

        model = TOOL_ARGUMENT_MODELS.get(name)
        if model is None:
            raise ToolPolicyError("Tool is not allowlisted", safe_code="TOOL_NOT_ALLOWED")

        if "user_id" in arguments:
            raise ToolPolicyError(
                "User identity cannot be supplied by the model",
                safe_code="USER_OVERRIDE_DENIED",
            )

        try:
            return model.model_validate(arguments)
        except ValidationError as error:
            raise ToolPolicyError(
                "Tool arguments failed validation",
                safe_code="INVALID_TOOL_ARGUMENTS",
            ) from error
