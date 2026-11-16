"""Configuration of the producer: the shared environment contract in common.settings."""

from __future__ import annotations

from common.settings import ProducerSettings, producer

ProducerConfig = ProducerSettings


def load_config() -> ProducerSettings:
    """Read and validate the producer variables; a missing one is named in the error."""
    return producer()
