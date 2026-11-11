# Kafka Event Contract

## Topics

- `terremotos_raw`: periodic USGS ingestion.
- `terremotos_replay`: accelerated historical 2025 ingestion.

Both topics use the same event schema. The topic name is persisted as
`source_topic` for traceability and is never silently merged in reporting.

## Event envelope

```json
{
  "id": "us7000example",
  "updated": 1735787045000,
  "time": 1735786800000,
  "mag": 4.2,
  "place": "Example",
  "geometry": {
    "type": "Point",
    "coordinates": [-70.1, 10.2, 12.0]
  },
  "properties": {},
  "source_topic": "terremotos_raw"
}
```

`id`, `updated`, `time`, `mag` and `geometry.coordinates` are validated by the WAF.
Coordinates are longitude, latitude, optional depth. Unknown original properties
must remain available for audit.

The `Frescura` rule rejects `time` values more than 300 seconds in the future.
For `terremotos_raw`, events older than 7 days are also quarantined; valid
historical dates remain allowed on `terremotos_replay`.

## Processing contract

1. Consumer parses JSON; malformed JSON is quarantined as a Validez failure.
2. WAF validates required fields and ranges.
3. Invalid events are inserted in `cuarentena` in one PostgreSQL transaction.
4. Valid events are enriched by Point in Polygon; no polygon match means
   `Sin país asignado`.
5. Valid events execute an idempotent upsert keyed by `id` and guarded by
   `updated`.
6. PostgreSQL transaction commits.
7. Consumer manually commits the Kafka offset.

A failure before step 6 MUST leave the offset uncommitted. A failure between steps
6 and 7 is safe to retry because the database write is idempotent.
