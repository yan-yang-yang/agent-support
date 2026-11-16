from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path


@dataclass(frozen=True, slots=True)
class Settings:
    database_path: Path
    default_user_id: str = "demo-user"
    stream_character_delay: float = 0.018

    @classmethod
    def from_environment(cls) -> "Settings":
        default_path = Path(__file__).resolve().parent.parent / "data" / "agent-support.db"
        return cls(
            database_path=Path(os.getenv("APP_DATABASE_PATH", default_path)),
            default_user_id=os.getenv("APP_DEFAULT_USER_ID", "demo-user"),
            stream_character_delay=float(os.getenv("APP_STREAM_CHARACTER_DELAY", "0.018")),
        )
