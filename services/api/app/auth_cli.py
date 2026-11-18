from __future__ import annotations

import argparse
from urllib.parse import quote

from .auth import SignedAuthService
from .config import Settings


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Create a short-lived signed H5 launch URL",
    )
    parser.add_argument("--base-url", required=True)
    parser.add_argument("--user-id", required=True)
    parser.add_argument("--display-name", required=True)
    args = parser.parse_args()

    settings = Settings.from_environment()
    service = SignedAuthService(
        secret=settings.auth_secret,
        launch_ttl_seconds=settings.auth_launch_ttl_seconds,
        session_ttl_seconds=settings.auth_session_ttl_seconds,
    )
    token = service.issue_launch_token(
        user_id=args.user_id,
        display_name=args.display_name,
    )
    base_url = args.base_url.rstrip("/")
    print(f"{base_url}/#launch_token={quote(token)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
