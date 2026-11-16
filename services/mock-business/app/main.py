from __future__ import annotations

import os
from pathlib import Path

from fastapi import FastAPI

from .routes import router
from .store import SeedStore


def create_app(
    *,
    internal_token: str | None = None,
    seed_path: Path | None = None,
) -> FastAPI:
    app = FastAPI(title="Umbrella Mock Business API", version="0.1.0")
    app.state.internal_token = internal_token or os.getenv(
        "MOCK_BUSINESS_INTERNAL_TOKEN",
        "dev-internal-token",
    )
    app.state.store = SeedStore(seed_path) if seed_path else SeedStore.from_default_seed()
    app.include_router(router)

    @app.get("/health")
    def health() -> dict[str, str]:
        return {"status": "ok", "service": "umbrella-mock-business"}

    return app


app = create_app()
