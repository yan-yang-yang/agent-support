from __future__ import annotations

import os
from dataclasses import dataclass, field
from pathlib import Path


DEFAULT_AUTH_SECRET = "dev-auth-secret-change-me-32-bytes"


def env_bool(name: str, default: bool) -> bool:
    value = os.getenv(name)
    if value is None:
        return default
    normalized = value.strip().lower()
    if normalized in {"1", "true", "yes", "on"}:
        return True
    if normalized in {"0", "false", "no", "off"}:
        return False
    raise ValueError(f"{name} must be a boolean")


@dataclass(frozen=True, slots=True)
class Settings:
    database_path: Path
    environment: str = "development"
    default_user_id: str = "demo-user"
    auth_secret: str = field(default=DEFAULT_AUTH_SECRET, repr=False)
    auth_required: bool = False
    auth_cookie_name: str = "support_session"
    auth_cookie_secure: bool = False
    auth_launch_ttl_seconds: int = 300
    auth_session_ttl_seconds: int = 86_400
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
    agent_max_tool_calls: int = 6
    memory_recent_message_limit: int = 6
    memory_summary_max_chars: int = 1600
    memory_max_long_term_items: int = 12

    @classmethod
    def from_environment(cls) -> "Settings":
        default_path = Path(__file__).resolve().parent.parent / "data" / "agent-support.db"
        return cls(
            database_path=Path(os.getenv("APP_DATABASE_PATH", default_path)),
            environment=os.getenv("APP_ENVIRONMENT", "development"),
            default_user_id=os.getenv("APP_DEFAULT_USER_ID", "demo-user"),
            auth_secret=os.getenv(
                "APP_AUTH_SECRET",
                DEFAULT_AUTH_SECRET,
            ),
            auth_required=env_bool("APP_AUTH_REQUIRED", False),
            auth_cookie_name=os.getenv("APP_AUTH_COOKIE_NAME", "support_session"),
            auth_cookie_secure=env_bool("APP_AUTH_COOKIE_SECURE", False),
            auth_launch_ttl_seconds=int(os.getenv("APP_AUTH_LAUNCH_TTL_SECONDS", "300")),
            auth_session_ttl_seconds=int(os.getenv("APP_AUTH_SESSION_TTL_SECONDS", "86400")),
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
            agent_max_tool_calls=int(os.getenv("AGENT_MAX_TOOL_CALLS", "6")),
            memory_recent_message_limit=int(os.getenv("MEMORY_RECENT_MESSAGE_LIMIT", "6")),
            memory_summary_max_chars=int(os.getenv("MEMORY_SUMMARY_MAX_CHARS", "1600")),
            memory_max_long_term_items=int(os.getenv("MEMORY_MAX_LONG_TERM_ITEMS", "12")),
        )
