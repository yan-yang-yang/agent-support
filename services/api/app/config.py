from __future__ import annotations

import os
from dataclasses import dataclass, field
from pathlib import Path


@dataclass(frozen=True, slots=True)
class Settings:
    database_path: Path
    environment: str = "development"
    default_user_id: str = "demo-user"
    stream_character_delay: float = 0.018
    business_base_url: str = "http://127.0.0.1:8010"
    business_internal_token: str = "dev-internal-token"
    business_timeout_seconds: float = 3.0
    model_provider: str = "fake"
    openai_base_url: str = "https://api.openai.com/v1"
    openai_api_key: str | None = field(default=None, repr=False)
    openai_model: str | None = None
    model_timeout_seconds: float = 30.0
    model_max_retries: int = 2
    model_temperature: float | None = 0.2
    model_max_output_tokens: int | None = 600

    @classmethod
    def from_environment(cls) -> "Settings":
        default_path = Path(__file__).resolve().parent.parent / "data" / "agent-support.db"
        return cls(
            database_path=Path(os.getenv("APP_DATABASE_PATH", default_path)),
            environment=os.getenv("APP_ENVIRONMENT", "development"),
            default_user_id=os.getenv("APP_DEFAULT_USER_ID", "demo-user"),
            stream_character_delay=float(os.getenv("APP_STREAM_CHARACTER_DELAY", "0.018")),
            business_base_url=os.getenv("APP_BUSINESS_BASE_URL", "http://127.0.0.1:8010"),
            business_internal_token=os.getenv(
                "APP_BUSINESS_INTERNAL_TOKEN",
                "dev-internal-token",
            ),
            business_timeout_seconds=float(os.getenv("APP_BUSINESS_TIMEOUT_SECONDS", "3")),
            model_provider=os.getenv("MODEL_PROVIDER", "fake"),
            openai_base_url=os.getenv("OPENAI_BASE_URL", "https://api.openai.com/v1"),
            openai_api_key=os.getenv("OPENAI_API_KEY") or None,
            openai_model=os.getenv("OPENAI_MODEL") or None,
            model_timeout_seconds=float(os.getenv("MODEL_TIMEOUT_SECONDS", "30")),
            model_max_retries=int(os.getenv("MODEL_MAX_RETRIES", "2")),
            model_temperature=float(os.getenv("MODEL_TEMPERATURE", "0.2")),
            model_max_output_tokens=int(os.getenv("MODEL_MAX_OUTPUT_TOKENS", "600")),
        )
