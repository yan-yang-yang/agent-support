from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path


@dataclass(frozen=True, slots=True)
class Settings:
    database_path: Path
    default_user_id: str = "demo-user"
    stream_character_delay: float = 0.018
    business_base_url: str = "http://127.0.0.1:8010"
    business_internal_token: str = "dev-internal-token"
    business_timeout_seconds: float = 3.0

    @classmethod
    def from_environment(cls) -> "Settings":
        default_path = Path(__file__).resolve().parent.parent / "data" / "agent-support.db"
        return cls(
            database_path=Path(os.getenv("APP_DATABASE_PATH", default_path)),
            default_user_id=os.getenv("APP_DEFAULT_USER_ID", "demo-user"),
            stream_character_delay=float(os.getenv("APP_STREAM_CHARACTER_DELAY", "0.018")),
            business_base_url=os.getenv("APP_BUSINESS_BASE_URL", "http://127.0.0.1:8010"),
            business_internal_token=os.getenv(
                "APP_BUSINESS_INTERNAL_TOKEN",
                "dev-internal-token",
            ),
            business_timeout_seconds=float(os.getenv("APP_BUSINESS_TIMEOUT_SECONDS", "3")),
        )
