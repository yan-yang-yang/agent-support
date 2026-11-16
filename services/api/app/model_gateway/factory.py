from __future__ import annotations

from typing import TYPE_CHECKING

from .fake_adapter import FakeModelGateway
from .openai_adapter import OpenAICompatibleAdapter
from .protocol import ModelGateway
from .repository import ModelCallRepository

if TYPE_CHECKING:
    from ..config import Settings


def create_model_gateway(
    settings: "Settings",
    repository: ModelCallRepository,
) -> ModelGateway:
    provider = settings.model_provider.lower().strip()
    if provider == "fake":
        if settings.environment.lower() == "production":
            raise ValueError("MODEL_PROVIDER=fake is not allowed in production")
        return FakeModelGateway(
            repository=repository,
            character_delay=settings.stream_character_delay,
        )

    if provider in {"openai", "openai-compatible"}:
        if not settings.openai_api_key:
            raise ValueError("OPENAI_API_KEY is required when MODEL_PROVIDER=openai")
        if not settings.openai_model:
            raise ValueError("OPENAI_MODEL is required when MODEL_PROVIDER=openai")
        return OpenAICompatibleAdapter(
            base_url=settings.openai_base_url,
            api_key=settings.openai_api_key,
            model=settings.openai_model,
            repository=repository,
            timeout_seconds=settings.model_timeout_seconds,
            max_retries=settings.model_max_retries,
            temperature=settings.model_temperature,
            max_output_tokens=settings.model_max_output_tokens,
        )

    raise ValueError(f"Unsupported MODEL_PROVIDER: {settings.model_provider}")
