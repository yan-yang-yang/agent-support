from __future__ import annotations

import pytest
from fastapi.testclient import TestClient

from app.auth import AuthTokenError, SignedAuthService
from app.config import Settings
from app.main import create_app


TEST_SECRET = "test-auth-secret-with-at-least-32-bytes"


def test_signed_launch_and_session_tokens_have_separate_scopes() -> None:
    service = SignedAuthService(secret=TEST_SECRET, launch_ttl_seconds=60, session_ttl_seconds=600)
    launch_token = service.issue_launch_token(
        user_id="customer-1001",
        display_name="小杨",
        now=1_000,
    )
    launch_identity = service.verify_launch_token(launch_token, now=1_030)

    assert launch_identity.user_id == "customer-1001"
    assert launch_identity.display_name == "小杨"
    with pytest.raises(AuthTokenError, match="wrong scope"):
        service.verify_session_token(launch_token, now=1_030)


def test_signed_token_rejects_tampering_and_expiry() -> None:
    service = SignedAuthService(secret=TEST_SECRET, launch_ttl_seconds=60)
    token = service.issue_launch_token(user_id="customer-1001", display_name="小杨", now=1_000)
    encoded_header, encoded_payload, encoded_signature = token.split(".")
    replacement = "A" if encoded_signature[0] != "A" else "B"
    tampered = f"{encoded_header}.{encoded_payload}.{replacement}{encoded_signature[1:]}"

    with pytest.raises(AuthTokenError, match="signature"):
        service.verify_launch_token(tampered, now=1_030)
    with pytest.raises(AuthTokenError, match="expired"):
        service.verify_launch_token(token, now=1_060)


def test_demo_sessions_are_cookie_authenticated_and_isolated(tmp_path) -> None:
    app = create_app(
        Settings(
            database_path=tmp_path / "auth.db",
            auth_secret=TEST_SECRET,
            environment="demo",
        )
    )
    with TestClient(app) as client:
        first_identity = client.post(
            "/api/v1/auth/demo-session",
            json={"client_id": "browser-client-001", "profile": "demo-user"},
        )
        assert first_identity.status_code == 200
        assert first_identity.json()["user_id"] == "demo-user~browser-client-001"
        assert "HttpOnly" in first_identity.headers["set-cookie"]

        conversation_id = client.post("/api/v1/conversations", json={}).json()["id"]
        assert client.get("/api/v1/auth/me").json()["display_name"] == "演示用户"

        client.cookies.clear()
        second_identity = client.post(
            "/api/v1/auth/demo-session",
            json={"client_id": "browser-client-002", "profile": "demo-user"},
        )
        assert second_identity.status_code == 200
        assert client.get(f"/api/v1/conversations/{conversation_id}/messages").status_code == 404


def test_launch_token_exchange_sets_session_cookie(tmp_path) -> None:
    app = create_app(
        Settings(
            database_path=tmp_path / "launch.db",
            auth_secret=TEST_SECRET,
            auth_required=True,
        )
    )
    with TestClient(app) as client:
        launch_token = app.state.auth_service.issue_launch_token(
            user_id="customer-2002",
            display_name="签名用户",
        )
        response = client.post(
            "/api/v1/auth/exchange",
            json={"launch_token": launch_token},
        )

        assert response.status_code == 200
        assert response.json()["user_id"] == "customer-2002"
        assert client.get("/api/v1/auth/me").json()["source"] == "session"
        assert client.post("/api/v1/conversations", json={}).status_code == 201


def test_required_auth_rejects_demo_header(tmp_path) -> None:
    app = create_app(
        Settings(
            database_path=tmp_path / "required.db",
            auth_secret=TEST_SECRET,
            auth_required=True,
        )
    )
    with TestClient(app) as client:
        response = client.get(
            "/api/v1/conversations",
            headers={"X-Demo-User": "spoofed-user"},
        )
        assert response.status_code == 401
