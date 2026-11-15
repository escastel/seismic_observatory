"""A scriptable stand-in for the USGS feed and FDSN catalog (spec 003, research R13).

Standard library only. Tests start it in a thread:

    with FakeUsgs() as usgs:
        usgs.script("/feed", Reply.json(collection([...])), Reply(status=503))
        result = fetch(usgs.url("/feed"), ...)

Each request to a scripted path consumes the next reply; the last one repeats.
A reply may be a callable taking the RecordedRequest. PASS hands the request to
the fake catalog, which answers /count and /query from an in-memory event list
the way USGS does: [starttime, endtime) bounds, magnitude and type filters, and
HTTP 400 "N matching events exceeds search limit of M" instead of truncating.

As a service for evidence with the real stack (compose.dev.yaml, usgs-stub):

    python -m tests.support.usgs_stub --port 8080
"""

from __future__ import annotations

import argparse
import json
import threading
import time
from collections.abc import Callable, Sequence
from dataclasses import dataclass, field
from datetime import datetime, timezone
from email.utils import format_datetime
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from typing import Any
from urllib.parse import parse_qs, urlsplit

CATALOG_PATH = "/fdsnws/event/1"
LAST_MODIFIED = "Sun, 15 Nov 2026 01:20:53 GMT"


# --------------------------------------------------------------------- builders


def ms(moment: datetime | str) -> int:
    """Unix milliseconds of an aware datetime or an ISO string (UTC if naive)."""
    if isinstance(moment, str):
        moment = datetime.fromisoformat(moment.replace("Z", "+00:00"))
    if moment.tzinfo is None:
        moment = moment.replace(tzinfo=timezone.utc)
    return int(moment.timestamp() * 1000)


def feature(
    event_id: str | None,
    time: datetime | str | int = "2026-11-14T10:00:00Z",
    updated: datetime | str | int | None = None,
    *,
    mag: float | None = 4.2,
    event_type: str | None = "earthquake",
    longitude: float = -3.7,
    latitude: float = 40.4,
    depth: float | None = 10.0,
    place: str | None = "Test place",
) -> dict[str, Any]:
    """A GeoJSON Feature shaped like the USGS ones."""
    time_ms = time if isinstance(time, int) else ms(time)
    updated_ms = time_ms + 60_000 if updated is None else (updated if isinstance(updated, int) else ms(updated))
    properties: dict[str, Any] = {
        "mag": mag,
        "place": place,
        "time": time_ms,
        "updated": updated_ms,
        "tz": None,
        "status": "reviewed",
        "magType": "ml",
        "type": event_type,
        "title": f"M {mag} - {place}",
    }
    if event_type is None:
        del properties["type"]
    item: dict[str, Any] = {
        "type": "Feature",
        "properties": properties,
        "geometry": {"type": "Point", "coordinates": [longitude, latitude, depth]},
    }
    if event_id is not None:
        item["id"] = event_id
    return item


def collection(features: Sequence[Any], generated: int | None = None, url: str = "stub") -> dict[str, Any]:
    """A FeatureCollection with USGS-like metadata."""
    return {
        "type": "FeatureCollection",
        "metadata": {
            "generated": generated if generated is not None else int(time.time() * 1000),
            "url": url,
            "title": "Stub earthquakes",
            "status": 200,
            "api": "stub",
            "count": len(features),
        },
        "features": list(features),
    }


# ---------------------------------------------------------------------- replies


@dataclass
class Reply:
    status: int = 200
    body: bytes = b""
    headers: dict[str, str] = field(default_factory=dict)
    delay: float = 0.0                 # seconds to wait before answering
    conditional: bool = False          # answer 304 when If-Modified-Since is present

    @classmethod
    def json(cls, payload: Any, status: int = 200, **kwargs: Any) -> Reply:
        headers = {"Content-Type": "application/json; charset=utf-8", "Last-Modified": LAST_MODIFIED}
        headers.update(kwargs.pop("headers", {}))
        return cls(status=status, body=json.dumps(payload).encode("utf-8"), headers=headers, **kwargs)

    @classmethod
    def text(cls, text: str, status: int = 200, **kwargs: Any) -> Reply:
        headers = {"Content-Type": "text/plain; charset=utf-8"}
        headers.update(kwargs.pop("headers", {}))
        return cls(status=status, body=text.encode("utf-8"), headers=headers, **kwargs)


PASS = object()  # delegate to the fake catalog


@dataclass
class RecordedRequest:
    path: str
    params: dict[str, str]
    headers: dict[str, str]
    at: float


ReplySource = Reply | Callable[[RecordedRequest], "Reply | object"] | object


# ----------------------------------------------------------------- fake catalog


def _instant(value: str) -> int:
    return ms(value)


class FakeCatalog:
    """In-memory FDSN event service: /count and /query with USGS semantics."""

    def __init__(self, events: Sequence[dict[str, Any]] = (), max_allowed: int = 20_000) -> None:
        self.events: list[dict[str, Any]] = list(events)
        self.max_allowed = max_allowed
        # Optional hook to tamper with a /query answer (e.g. drop events).
        self.query_filter: Callable[[list[dict[str, Any]]], list[dict[str, Any]]] | None = None

    def matching(self, params: dict[str, str]) -> list[dict[str, Any]]:
        start = _instant(params["starttime"]) if "starttime" in params else None
        end = _instant(params["endtime"]) if "endtime" in params else None
        min_mag = float(params["minmagnitude"]) if "minmagnitude" in params else None
        event_type = params.get("eventtype")
        selected = []
        for item in self.events:
            props = item["properties"]
            if start is not None and props["time"] < start:
                continue
            if end is not None and props["time"] >= end:
                continue
            if min_mag is not None and (props.get("mag") is None or props["mag"] < min_mag):
                continue
            if event_type is not None and props.get("type") != event_type:
                continue
            selected.append(item)
        return sorted(selected, key=lambda item: item["properties"]["time"])

    def answer(self, request: RecordedRequest) -> Reply:
        endpoint = request.path.rsplit("/", 1)[-1]
        matching = self.matching(request.params)
        if endpoint == "count":
            return Reply.json({"count": len(matching), "maxAllowed": self.max_allowed})
        if endpoint == "query":
            if "limit" in request.params:
                return Reply.text("Error 400: Bad Request\n\nlimit is not used by this project", status=400)
            if len(matching) > self.max_allowed:
                return Reply.text(
                    f"Error 400: Bad Request\n\n{len(matching)} matching events exceeds search limit of "
                    f"{self.max_allowed}. Modify the search to match fewer events.",
                    status=400,
                )
            if self.query_filter is not None:
                matching = self.query_filter(matching)
            return Reply.json(collection(matching, url=request.path))
        return Reply.text("Error 404: Not Found", status=404)


# ----------------------------------------------------------------------- server


class FakeUsgs:
    """HTTP server in a background thread; use as a context manager."""

    def __init__(self, catalog: FakeCatalog | None = None, host: str = "127.0.0.1", port: int = 0) -> None:
        self.catalog = catalog
        self.routes: dict[str, list[ReplySource]] = {}
        self.requests: list[RecordedRequest] = []
        self._lock = threading.Lock()
        self._server = ThreadingHTTPServer((host, port), self._handler_class())
        self._server.daemon_threads = True
        self._thread: threading.Thread | None = None

    # -- scripting
    def script(self, path: str, *replies: ReplySource) -> None:
        if not replies:
            raise ValueError("script() needs at least one reply")
        with self._lock:
            self.routes[path] = list(replies)

    def url(self, path: str = "") -> str:
        host, port = self._server.server_address[:2]
        return f"http://{host}:{port}{path}"

    @property
    def catalog_url(self) -> str:
        return self.url(CATALOG_PATH)

    def requests_to(self, path_suffix: str) -> list[RecordedRequest]:
        with self._lock:
            return [request for request in self.requests if request.path.endswith(path_suffix)]

    # -- lifecycle
    def start(self) -> FakeUsgs:
        self._thread = threading.Thread(target=self._server.serve_forever, name="fake-usgs", daemon=True)
        self._thread.start()
        return self

    def stop(self) -> None:
        self._server.shutdown()
        self._server.server_close()

    def __enter__(self) -> FakeUsgs:
        return self.start()

    def __exit__(self, *exc: object) -> None:
        self.stop()

    # -- request handling
    def _next_reply(self, request: RecordedRequest) -> Reply:
        with self._lock:
            self.requests.append(request)
            queue = self.routes.get(request.path)
            source: ReplySource = PASS
            if queue:
                source = queue.pop(0) if len(queue) > 1 else queue[0]
        reply = source(request) if callable(source) else source
        if reply is PASS:
            if self.catalog is None:
                return Reply.text("Error 404: Not Found", status=404)
            return self.catalog.answer(request)
        assert isinstance(reply, Reply)
        return reply

    def _handler_class(self) -> type[BaseHTTPRequestHandler]:
        stub = self

        class Handler(BaseHTTPRequestHandler):
            protocol_version = "HTTP/1.1"

            def do_GET(self) -> None:  # noqa: N802 - http.server API
                parts = urlsplit(self.path)
                params = {key: values[-1] for key, values in parse_qs(parts.query).items()}
                request = RecordedRequest(parts.path, params, {k: v for k, v in self.headers.items()}, time.time())
                reply = stub._next_reply(request)
                if reply.delay:
                    time.sleep(reply.delay)
                if reply.conditional and "If-Modified-Since" in self.headers:
                    reply = Reply(status=304, headers={"Last-Modified": reply.headers.get("Last-Modified", LAST_MODIFIED)})
                try:
                    self.send_response(reply.status)
                    for name, value in reply.headers.items():
                        self.send_header(name, value)
                    self.send_header("Content-Length", str(len(reply.body)))
                    self.end_headers()
                    if reply.body and reply.status != 304:
                        self.wfile.write(reply.body)
                except (BrokenPipeError, ConnectionResetError):
                    pass  # the client gave up (timeout tests)

            def log_message(self, format: str, *args: Any) -> None:  # noqa: A002 - silence
                return

        return Handler


# ---------------------------------------------------------- standalone service


def sample_collection() -> dict[str, Any]:
    now = datetime.now(timezone.utc)
    return collection(
        [
            feature("stub0001", now, mag=4.1, place="Stub earthquake"),
            feature("stub0002", now, mag=1.2, event_type="quarry blast", place="Stub quarry"),
        ]
    )


def standalone(port: int) -> FakeUsgs:
    """Fixed routes for evidence with the real stack (quickstart V3)."""
    usgs = FakeUsgs(FakeCatalog(), host="0.0.0.0", port=port)  # noqa: S104 - compose network only
    usgs.script("/feed/ok", lambda request: Reply.json(sample_collection(), conditional=True))
    usgs.script("/feed/fail-503", Reply.text("Service Unavailable", status=503))
    usgs.script("/feed/fail-429", Reply.text("Too Many Requests", status=429, headers={"Retry-After": "5"}))
    usgs.script("/feed/timeout", Reply(delay=600))
    usgs.script("/feed/not-json", Reply.text("<html>maintenance</html>"))
    usgs.script("/feed/bad-structure", Reply.json({"type": "Feature", "features": "none"}))
    return usgs


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Fake USGS source for tests and evidence")
    parser.add_argument("--port", type=int, default=8080)
    args = parser.parse_args(argv)
    usgs = standalone(args.port)
    print(f"fake USGS listening on port {args.port}", flush=True)
    try:
        usgs._server.serve_forever()
    except KeyboardInterrupt:
        pass
    return 0


if __name__ == "__main__":
    raise SystemExit(main())


__all__ = ["CATALOG_PATH", "PASS", "FakeCatalog", "FakeUsgs", "RecordedRequest", "Reply", "collection", "feature", "format_datetime", "ms"]
