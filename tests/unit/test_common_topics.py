"""Topic to schema routing (FR-012, contracts/database.md «Conexión»)."""

from __future__ import annotations

import pytest

from common.settings import TopicNames
from common.topics import UnknownTopicError, retention_ms, search_path_for

TOPICS = TopicNames()


@pytest.mark.parametrize("topic", ["earthquakes.live", "earthquakes.catalog"])
def test_real_topics_write_to_core(topic: str) -> None:
    assert search_path_for(topic, TOPICS) == "core"


def test_replay_topic_writes_to_replay_first() -> None:
    assert search_path_for("earthquakes.replay", TOPICS) == "replay, core"


@pytest.mark.parametrize("topic", ["earthquakes.unknown", "terremotos_raw", ""])
def test_unknown_topic_is_an_error_not_a_default(topic: str) -> None:
    with pytest.raises(UnknownTopicError):
        search_path_for(topic, TOPICS)


def test_configured_topic_names_are_honoured() -> None:
    custom = TopicNames(live="a", catalog="b", replay="c")
    assert [search_path_for(name, custom) for name in ("a", "b", "c")] == ["core", "core", "replay, core"]
    with pytest.raises(UnknownTopicError):
        search_path_for("earthquakes.live", custom)


def test_retention_of_seven_days() -> None:
    assert retention_ms(168) == 604_800_000
