"""In-memory stand-in for AIOKafkaProducer.send_and_wait."""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from typing import Any


@dataclass
class Sent:
    topic: str
    key: str
    value: dict[str, Any]


@dataclass
class FakeProducer:
    """Records every confirmed message. fail_after=n makes the (n+1)-th send fail."""

    fail_after: int | None = None
    sent: list[Sent] = field(default_factory=list)
    attempts: int = 0

    async def send_and_wait(self, topic: str, value: bytes | None = None, key: bytes | None = None, **_: Any) -> None:
        self.attempts += 1
        if self.fail_after is not None and len(self.sent) >= self.fail_after:
            raise ConnectionError("broker not available")
        assert value is not None and key is not None
        self.sent.append(Sent(topic, key.decode("utf-8"), json.loads(value)))

    async def start(self) -> None:
        return None

    async def stop(self) -> None:
        return None

    def keys(self, topic: str | None = None) -> list[str]:
        return [message.key for message in self.sent if topic is None or message.topic == topic]
