"""Minimal ASGI client: calls an ASGI app directly, without httpx or a server.

No lifespan is run; the caller prepares app.state itself.
"""

from __future__ import annotations

import json
from dataclasses import dataclass
from typing import Any
from urllib.parse import urlencode


@dataclass
class Response:
    status: int
    headers: dict[str, str]  # names in lowercase; repeated headers are joined with ", "
    body: bytes

    def json(self) -> Any:
        return json.loads(self.body)

    @property
    def text(self) -> str:
        return self.body.decode("utf-8")


def _query_string(params: dict[str, Any] | None) -> bytes:
    pairs: list[tuple[str, str]] = []
    for key, value in (params or {}).items():
        if value is None:
            continue
        values = value if isinstance(value, (list, tuple)) else [value]
        for item in values:
            pairs.append((key, str(item).lower() if isinstance(item, bool) else str(item)))
    return urlencode(pairs).encode("ascii")


async def call_asgi(
    app: Any,
    method: str,
    path: str,
    params: dict[str, Any] | None = None,
    headers: dict[str, str] | None = None,
    body: bytes = b"",
) -> Response:
    """Send one HTTP request to the ASGI app and collect the whole response."""
    raw_headers = [(b"host", b"testserver")]
    for name, value in (headers or {}).items():
        raw_headers.append((name.lower().encode("latin-1"), value.encode("latin-1")))
    if body:
        raw_headers.append((b"content-length", str(len(body)).encode("ascii")))
    scope = {
        "type": "http",
        "asgi": {"version": "3.0"},
        "http_version": "1.1",
        "method": method.upper(),
        "scheme": "http",
        "path": path,
        "raw_path": path.encode("utf-8"),
        "root_path": "",
        "query_string": _query_string(params),
        "headers": raw_headers,
        "client": ("127.0.0.1", 50000),
        "server": ("testserver", 80),
    }
    sent_body = False

    async def receive() -> dict[str, Any]:
        nonlocal sent_body
        if not sent_body:
            sent_body = True
            return {"type": "http.request", "body": body, "more_body": False}
        return {"type": "http.disconnect"}

    status = 0
    response_headers: dict[str, str] = {}
    chunks: list[bytes] = []

    async def send(message: dict[str, Any]) -> None:
        nonlocal status
        if message["type"] == "http.response.start":
            status = message["status"]
            for name, value in message.get("headers", []):
                key = name.decode("latin-1").lower()
                text = value.decode("latin-1")
                response_headers[key] = f"{response_headers[key]}, {text}" if key in response_headers else text
        elif message["type"] == "http.response.body":
            chunks.append(message.get("body", b""))

    await app(scope, receive, send)
    return Response(status, response_headers, b"".join(chunks))
