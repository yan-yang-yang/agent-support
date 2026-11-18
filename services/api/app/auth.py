from __future__ import annotations

import base64
import hashlib
import hmac
import json
import re
import time
from dataclasses import dataclass
from typing import Any, Literal
from uuid import uuid4


TokenPurpose = Literal["launch", "session"]
USER_ID_PATTERN = re.compile(r"^[A-Za-z0-9._~:-]{1,128}$")


class AuthTokenError(ValueError):
    pass


@dataclass(frozen=True, slots=True)
class UserIdentity:
    user_id: str
    display_name: str
    source: str


class SignedAuthService:
    def __init__(
        self,
        *,
        secret: str,
        issuer: str = "agent-support",
        launch_ttl_seconds: int = 300,
        session_ttl_seconds: int = 86_400,
    ) -> None:
        if len(secret.encode()) < 32:
            raise ValueError("APP_AUTH_SECRET must contain at least 32 bytes")
        self._secret = secret.encode()
        self._issuer = issuer
        self.launch_ttl_seconds = launch_ttl_seconds
        self.session_ttl_seconds = session_ttl_seconds

    def issue_launch_token(
        self,
        *,
        user_id: str,
        display_name: str,
        now: int | None = None,
    ) -> str:
        return self._issue(
            purpose="launch",
            user_id=user_id,
            display_name=display_name,
            ttl_seconds=self.launch_ttl_seconds,
            now=now,
        )

    def issue_session_token(
        self,
        identity: UserIdentity,
        *,
        now: int | None = None,
    ) -> str:
        return self._issue(
            purpose="session",
            user_id=identity.user_id,
            display_name=identity.display_name,
            ttl_seconds=self.session_ttl_seconds,
            now=now,
        )

    def verify_launch_token(self, token: str, *, now: int | None = None) -> UserIdentity:
        return self._verify(token, purpose="launch", now=now)

    def verify_session_token(self, token: str, *, now: int | None = None) -> UserIdentity:
        return self._verify(token, purpose="session", now=now)

    def _issue(
        self,
        *,
        purpose: TokenPurpose,
        user_id: str,
        display_name: str,
        ttl_seconds: int,
        now: int | None,
    ) -> str:
        self._validate_identity(user_id, display_name)
        issued_at = int(time.time()) if now is None else now
        header = {"alg": "HS256", "typ": "JWT"}
        payload = {
            "iss": self._issuer,
            "sub": user_id,
            "name": display_name,
            "purpose": purpose,
            "iat": issued_at,
            "exp": issued_at + ttl_seconds,
            "jti": str(uuid4()),
        }
        signing_input = f"{self._encode_json(header)}.{self._encode_json(payload)}"
        signature = hmac.new(self._secret, signing_input.encode(), hashlib.sha256).digest()
        return f"{signing_input}.{self._encode_bytes(signature)}"

    def _verify(
        self,
        token: str,
        *,
        purpose: TokenPurpose,
        now: int | None,
    ) -> UserIdentity:
        try:
            encoded_header, encoded_payload, encoded_signature = token.split(".")
        except ValueError as error:
            raise AuthTokenError("Malformed authentication token") from error

        signing_input = f"{encoded_header}.{encoded_payload}"
        expected = hmac.new(self._secret, signing_input.encode(), hashlib.sha256).digest()
        try:
            actual = self._decode_bytes(encoded_signature)
        except ValueError as error:
            raise AuthTokenError("Malformed authentication signature") from error
        if not hmac.compare_digest(actual, expected):
            raise AuthTokenError("Invalid authentication signature")

        header = self._decode_json(encoded_header)
        payload = self._decode_json(encoded_payload)
        if header != {"alg": "HS256", "typ": "JWT"}:
            raise AuthTokenError("Unsupported authentication token header")
        if payload.get("iss") != self._issuer or payload.get("purpose") != purpose:
            raise AuthTokenError("Authentication token has the wrong scope")

        current_time = int(time.time()) if now is None else now
        issued_at = payload.get("iat")
        expires_at = payload.get("exp")
        if not isinstance(issued_at, int) or not isinstance(expires_at, int):
            raise AuthTokenError("Authentication token timestamps are invalid")
        if issued_at > current_time + 60:
            raise AuthTokenError("Authentication token is not active")
        if expires_at <= current_time:
            raise AuthTokenError("Authentication token has expired")

        user_id = payload.get("sub")
        display_name = payload.get("name")
        if not isinstance(user_id, str) or not isinstance(display_name, str):
            raise AuthTokenError("Authentication token identity is invalid")
        self._validate_identity(user_id, display_name)
        return UserIdentity(user_id=user_id, display_name=display_name, source=purpose)

    @staticmethod
    def _validate_identity(user_id: str, display_name: str) -> None:
        if not USER_ID_PATTERN.fullmatch(user_id):
            raise AuthTokenError("User id contains unsupported characters")
        if not display_name.strip() or len(display_name) > 80:
            raise AuthTokenError("Display name is invalid")

    @classmethod
    def _encode_json(cls, value: dict[str, Any]) -> str:
        return cls._encode_bytes(
            json.dumps(value, ensure_ascii=False, separators=(",", ":"), sort_keys=True).encode()
        )

    @staticmethod
    def _decode_json(value: str) -> dict[str, Any]:
        try:
            decoded = json.loads(SignedAuthService._decode_bytes(value))
        except (ValueError, json.JSONDecodeError, UnicodeDecodeError) as error:
            raise AuthTokenError("Authentication token JSON is invalid") from error
        if not isinstance(decoded, dict):
            raise AuthTokenError("Authentication token payload is invalid")
        return decoded

    @staticmethod
    def _encode_bytes(value: bytes) -> str:
        return base64.urlsafe_b64encode(value).rstrip(b"=").decode()

    @staticmethod
    def _decode_bytes(value: str) -> bytes:
        padding = "=" * (-len(value) % 4)
        return base64.b64decode(value + padding, altchars=b"-_", validate=True)
