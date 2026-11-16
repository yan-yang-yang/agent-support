from __future__ import annotations

import pytest
from fastapi.testclient import TestClient

from app.main import create_app


@pytest.fixture
def client() -> TestClient:
    with TestClient(create_app(internal_token="test-internal-token")) as test_client:
        test_client.headers["X-Internal-Token"] = "test-internal-token"
        yield test_client
