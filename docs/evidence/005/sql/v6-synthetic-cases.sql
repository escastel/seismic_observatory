-- V6: resultado de cada caso sintético (contracts/synthetic-cases.md).
\echo '== resultado de cada mensaje, en orden de llegada'
SELECT kafka_offset, event_id, updated_at, outcome
FROM replay.message_log WHERE event_id LIKE 'synthetic-replay-%' OR outcome = 'quarantined'
ORDER BY kafka_offset;

\echo '== recuento por resultado (esperado: duplicate 1, new 3, quarantined 1, revised 1, stale 1)'
SELECT outcome, count(*) FROM replay.message_log GROUP BY outcome ORDER BY outcome;

\echo '== estado actual: la revisión tomó la versión nueva y la antigua tardía no retrocedió (updated_at = U2 = 13:30)'
SELECT event_id, magnitude, updated_at, quality_flags FROM replay.event_current ORDER BY event_id;

\echo '== versiones conservadas (esperado: first 1, revised 2, stale 2)'
SELECT event_id, count(*) AS versions FROM replay.event_version GROUP BY event_id ORDER BY event_id;

\echo '== cuarentena (esperado: 1 fila sintética con coordinates_out_of_range y el original)'
SELECT event_id, reason_codes, is_synthetic, payload IS NOT NULL AS has_original FROM replay.quarantine;

\echo '== nada sintético en core (esperado: 0 en cada tabla)'
SELECT (SELECT count(*) FROM core.event_current   WHERE event_id LIKE 'synthetic-replay-%') AS event_current,
       (SELECT count(*) FROM core.event_version   WHERE event_id LIKE 'synthetic-replay-%') AS event_version,
       (SELECT count(*) FROM core.quarantine      WHERE event_id LIKE 'synthetic-replay-%') AS quarantine,
       (SELECT count(*) FROM core.message_log     WHERE event_id LIKE 'synthetic-replay-%') AS message_log;
