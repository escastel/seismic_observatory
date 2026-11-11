from tests.integration.load_test import percentile


def test_percentile_is_deterministic_for_latency_samples() -> None:
    assert percentile([0.1, 0.2, 0.3, 0.4], 95) == 0.4
