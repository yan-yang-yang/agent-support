#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import sys
from collections import Counter
from http.cookiejar import CookieJar
from urllib.error import HTTPError, URLError
from urllib.request import HTTPCookieProcessor, Request, build_opener, urlopen
from uuid import uuid4


def request_json(
    url: str,
    *,
    method: str = "GET",
    payload: dict[str, object] | None = None,
    opener,
) -> object:
    body = json.dumps(payload).encode() if payload is not None else None
    request = Request(
        url,
        data=body,
        method=method,
        headers={
            "Content-Type": "application/json",
        },
    )
    with opener.open(request, timeout=30) as response:
        return json.loads(response.read().decode())


def stream_events(
    url: str,
    *,
    payload: dict[str, object],
    opener,
) -> list[tuple[str, dict[str, object]]]:
    request = Request(
        url,
        data=json.dumps(payload).encode(),
        method="POST",
        headers={
            "Accept": "text/event-stream",
            "Content-Type": "application/json",
        },
    )
    with opener.open(request, timeout=60) as response:
        text = response.read().decode()

    events: list[tuple[str, dict[str, object]]] = []
    for block in text.strip().split("\n\n"):
        event_name = ""
        data_lines: list[str] = []
        for line in block.splitlines():
            if line.startswith("event: "):
                event_name = line.removeprefix("event: ")
            elif line.startswith("data: "):
                data_lines.append(line.removeprefix("data: "))
        if event_name and data_lines:
            events.append((event_name, json.loads("\n".join(data_lines))))
    return events


def run(base_url: str) -> None:
    base_url = base_url.rstrip("/")
    client_id = f"smoke-client-{uuid4().hex[:8]}"
    request_id = f"smoke-request-{uuid4()}"
    opener = build_opener(HTTPCookieProcessor(CookieJar()))

    with urlopen(f"{base_url}/health", timeout=10) as response:
        if response.status != 200:
            raise RuntimeError(f"web health returned {response.status}")

    identity = request_json(
        f"{base_url}/api/v1/auth/demo-session",
        method="POST",
        payload={"client_id": client_id, "profile": "demo-user"},
        opener=opener,
    )
    if not isinstance(identity, dict) or "user_id" not in identity:
        raise RuntimeError("demo authentication returned an invalid response")

    conversation = request_json(
        f"{base_url}/api/v1/conversations",
        method="POST",
        payload={},
        opener=opener,
    )
    if not isinstance(conversation, dict) or "id" not in conversation:
        raise RuntimeError("conversation creation returned an invalid response")

    events = stream_events(
        f"{base_url}/api/v1/conversations/{conversation['id']}/messages:stream",
        payload={"content": "附近哪里可以还伞？", "request_id": request_id},
        opener=opener,
    )
    event_names = [name for name, _ in events]
    required_events = {
        "message.started",
        "tool.started",
        "tool.completed",
        "assistant.delta",
        "business_card",
        "assistant.completed",
    }
    missing = sorted(required_events - set(event_names))
    if missing:
        raise RuntimeError(f"SSE events missing: {', '.join(missing)}")

    completed = next(data for name, data in events if name == "assistant.completed")
    if not completed.get("traceId"):
        raise RuntimeError("assistant.completed did not include traceId")

    traces = request_json(
        f"{base_url}/api/v1/observability/traces?limit=10",
        opener=opener,
    )
    if not isinstance(traces, list) or not any(
        trace.get("request_id") == request_id and trace.get("status") == "completed"
        for trace in traces
    ):
        raise RuntimeError("completed trace was not found")

    second_opener = build_opener(HTTPCookieProcessor(CookieJar()))
    second_identity = request_json(
        f"{base_url}/api/v1/auth/demo-session",
        method="POST",
        payload={"client_id": f"{client_id}-other", "profile": "demo-user"},
        opener=second_opener,
    )
    try:
        request_json(
            f"{base_url}/api/v1/conversations/{conversation['id']}/messages",
            opener=second_opener,
        )
    except HTTPError as error:
        if error.code != 404:
            raise
    else:
        raise RuntimeError("a second authenticated user could read the first user's conversation")

    print(
        json.dumps(
            {
                "status": "passed",
                "base_url": base_url,
                "auth_user_id": identity["user_id"],
                "isolated_from_user_id": second_identity["user_id"],
                "conversation_id": conversation["id"],
                "request_id": request_id,
                "trace_id": completed["traceId"],
                "event_counts": dict(Counter(event_names)),
            },
            ensure_ascii=False,
            indent=2,
        )
    )


def main() -> int:
    parser = argparse.ArgumentParser(description="Smoke-test a deployed Agent Support stack")
    parser.add_argument("base_url", nargs="?", default="http://127.0.0.1")
    args = parser.parse_args()
    try:
        run(args.base_url)
    except (HTTPError, URLError, TimeoutError, RuntimeError) as error:
        print(f"smoke test failed: {error}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
