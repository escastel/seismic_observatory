"""One log format for every service: UTC time, level, service and logger."""

from __future__ import annotations

import logging
import time

FORMAT = "%(asctime)s %(levelname)s service=%(service)s %(name)s %(message)s"
DATE_FORMAT = "%Y-%m-%dT%H:%M:%S"


class _UtcFormatter(logging.Formatter):
    converter = time.gmtime

    def formatTime(self, record: logging.LogRecord, datefmt: str | None = None) -> str:  # noqa: N802
        return f"{super().formatTime(record, datefmt)}.{int(record.msecs):03d}Z"


class _ServiceFilter(logging.Filter):
    def __init__(self, service: str) -> None:
        super().__init__()
        self.service = service

    def filter(self, record: logging.LogRecord) -> bool:
        record.service = self.service
        return True


def configure(service: str, level: int = logging.INFO) -> None:
    """Install the shared format on the root logger (idempotent)."""
    handler = logging.StreamHandler()
    handler.setFormatter(_UtcFormatter(FORMAT, DATE_FORMAT))
    handler.addFilter(_ServiceFilter(service))
    root = logging.getLogger()
    root.handlers[:] = [handler]
    root.setLevel(level)
