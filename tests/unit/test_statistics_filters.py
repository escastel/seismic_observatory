import asyncio
from datetime import datetime, timezone

from api.app.queries import daily_average_2025, depth_stats, magnitude_stats, missing_magnitude
from api.app.schemas import EventFilters


class RecordingPool:
    def __init__(self) -> None:
        self.fetch_queries: list[tuple[str, tuple[object, ...]]] = []
        self.fetchval_queries: list[tuple[str, tuple[object, ...]]] = []

    async def fetch(self, query: str, *args: object) -> list[object]:
        self.fetch_queries.append((query, args))
        return []

    async def fetchval(self, query: str, *args: object) -> object:
        self.fetchval_queries.append((query, args))
        return 0


def test_all_distribution_queries_apply_the_same_date_and_magnitude_filters() -> None:
    pool = RecordingPool()
    filters = EventFilters(
        date_from=datetime(2026, 2, 1, tzinfo=timezone.utc),
        date_to=datetime(2026, 4, 1, tzinfo=timezone.utc),
        end_exclusive=True,
        min_magnitude=4,
    )

    async def run() -> None:
        await magnitude_stats(pool, filters)
        await depth_stats(pool, filters)
        await daily_average_2025(pool, filters)
        await missing_magnitude(pool, filters)

    asyncio.run(run())

    queries = [query for query, _ in pool.fetch_queries + pool.fetchval_queries]
    arguments = [args for _, args in pool.fetch_queries + pool.fetchval_queries]
    assert len(queries) == 4
    assert all("f.event_time >= $1" in query for query in queries)
    assert all("f.event_time < $2" in query for query in queries)
    assert all("f.magnitude >= $3" in query for query in queries)
    assert all(args[0].year == 2026 for args in arguments)
    assert all(args[1].year == 2026 for args in arguments)
    assert all(args[2] == 4 for args in arguments)
