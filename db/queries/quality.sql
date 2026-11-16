-- Consultas de calidad de los datos (spec 004, R12 y data-model.md §6).
-- Cada consulta va precedida de su comentario de nombre y de una línea que indica su denominador.
-- Ejecución: psql -f db/queries/quality.sql  (o copiar una consulta concreta).
-- Todas excluyen lo sintético por defecto; las variantes «synthetic-only» cuentan solo lo sintético.
-- Sin contadores acumulados: todo se calcula de lo almacenado.

-- name: messages-by-outcome
-- Denominador: mensajes recibidos (message_log, attempt = 0, sin sintéticos).
SELECT m.outcome, count(*) AS messages
FROM core.message_log m
WHERE m.attempt = 0
  AND (m.event_id IS NULL OR m.event_id NOT LIKE 'synthetic-%')
  AND NOT EXISTS (SELECT 1 FROM core.quarantine q
                  WHERE q.kafka_topic = m.kafka_topic AND q.kafka_partition = m.kafka_partition
                    AND q.kafka_offset = m.kafka_offset AND q.is_synthetic)
  AND NOT EXISTS (SELECT 1 FROM core.event_current e
                  WHERE e.event_id = m.event_id AND 'synthetic' = ANY (e.quality_flags))
GROUP BY m.outcome
ORDER BY m.outcome;

-- name: messages-by-outcome-synthetic-only
-- Denominador: mensajes recibidos sintéticos (message_log, attempt = 0).
SELECT m.outcome, count(*) AS messages
FROM core.message_log m
WHERE m.attempt = 0
  AND (coalesce(m.event_id LIKE 'synthetic-%', false)
       OR EXISTS (SELECT 1 FROM core.quarantine q
                  WHERE q.kafka_topic = m.kafka_topic AND q.kafka_partition = m.kafka_partition
                    AND q.kafka_offset = m.kafka_offset AND q.is_synthetic)
       OR EXISTS (SELECT 1 FROM core.event_current e
                  WHERE e.event_id = m.event_id AND 'synthetic' = ANY (e.quality_flags)))
GROUP BY m.outcome
ORDER BY m.outcome;

-- name: reprocessed-by-outcome
-- Denominador: mensajes reprocesados (message_log, attempt = 1, sin sintéticos).
SELECT m.outcome, count(*) AS messages
FROM core.message_log m
WHERE m.attempt = 1
  AND (m.event_id IS NULL OR m.event_id NOT LIKE 'synthetic-%')
  AND NOT EXISTS (SELECT 1 FROM core.quarantine q
                  WHERE q.kafka_topic = m.kafka_topic AND q.kafka_partition = m.kafka_partition
                    AND q.kafka_offset = m.kafka_offset AND q.is_synthetic)
  AND NOT EXISTS (SELECT 1 FROM core.event_current e
                  WHERE e.event_id = m.event_id AND 'synthetic' = ANY (e.quality_flags))
GROUP BY m.outcome
ORDER BY m.outcome;

-- name: reprocessed-by-outcome-synthetic-only
-- Denominador: mensajes reprocesados sintéticos (message_log, attempt = 1).
SELECT m.outcome, count(*) AS messages
FROM core.message_log m
WHERE m.attempt = 1
  AND (coalesce(m.event_id LIKE 'synthetic-%', false)
       OR EXISTS (SELECT 1 FROM core.quarantine q
                  WHERE q.kafka_topic = m.kafka_topic AND q.kafka_partition = m.kafka_partition
                    AND q.kafka_offset = m.kafka_offset AND q.is_synthetic)
       OR EXISTS (SELECT 1 FROM core.event_current e
                  WHERE e.event_id = m.event_id AND 'synthetic' = ANY (e.quality_flags)))
GROUP BY m.outcome
ORDER BY m.outcome;

-- name: received-check
-- Denominador: mensajes recibidos (attempt = 0, sin sintéticos); la diferencia debe ser 0.
SELECT received, sum_of_outcomes, received - sum_of_outcomes AS difference
FROM (
    SELECT count(*) AS received,
           count(*) FILTER (WHERE m.outcome = 'new')
         + count(*) FILTER (WHERE m.outcome = 'revised')
         + count(*) FILTER (WHERE m.outcome = 'stale')
         + count(*) FILTER (WHERE m.outcome = 'duplicate')
         + count(*) FILTER (WHERE m.outcome = 'excluded')
         + count(*) FILTER (WHERE m.outcome = 'quarantined') AS sum_of_outcomes
    FROM core.message_log m
    WHERE m.attempt = 0
      AND (m.event_id IS NULL OR m.event_id NOT LIKE 'synthetic-%')
      AND NOT EXISTS (SELECT 1 FROM core.quarantine q
                      WHERE q.kafka_topic = m.kafka_topic AND q.kafka_partition = m.kafka_partition
                        AND q.kafka_offset = m.kafka_offset AND q.is_synthetic)
      AND NOT EXISTS (SELECT 1 FROM core.event_current e
                      WHERE e.event_id = m.event_id AND 'synthetic' = ANY (e.quality_flags))
) t;

-- name: quarantine-by-reason
-- Denominador: mensajes rechazados; un mensaje con dos motivos cuenta en ambos (sin sintéticos).
SELECT reason, count(*) AS messages
FROM core.quarantine q
CROSS JOIN LATERAL unnest(q.reason_codes) AS reason
WHERE NOT q.is_synthetic
GROUP BY reason
ORDER BY messages DESC, reason;

-- name: quarantine-by-reason-synthetic-only
-- Denominador: mensajes rechazados sintéticos; un mensaje con dos motivos cuenta en ambos.
SELECT reason, count(*) AS messages
FROM core.quarantine q
CROSS JOIN LATERAL unnest(q.reason_codes) AS reason
WHERE q.is_synthetic
GROUP BY reason
ORDER BY messages DESC, reason;

-- name: quarantined-messages
-- Denominador: mensajes rechazados distintos (filas de cuarentena, sin sintéticos).
SELECT count(DISTINCT (q.kafka_topic, q.kafka_partition, q.kafka_offset)) AS rejected_messages,
       count(*) AS quarantine_rows,
       sum(cardinality(q.reason_codes)) AS reason_entries
FROM core.quarantine q
WHERE NOT q.is_synthetic;

-- name: quarantined-messages-synthetic-only
-- Denominador: mensajes rechazados distintos sintéticos (filas de cuarentena).
SELECT count(DISTINCT (q.kafka_topic, q.kafka_partition, q.kafka_offset)) AS rejected_messages,
       count(*) AS quarantine_rows,
       sum(cardinality(q.reason_codes)) AS reason_entries
FROM core.quarantine q
WHERE q.is_synthetic;

-- name: events-by-flag
-- Denominador: terremotos actuales (event_current, sin sintéticos); una fila por marca.
SELECT flag, count(*) AS events
FROM core.event_current e
CROSS JOIN LATERAL unnest(e.quality_flags) AS flag
WHERE NOT ('synthetic' = ANY (e.quality_flags))
GROUP BY flag
ORDER BY events DESC, flag;

-- name: events-by-flag-synthetic-only
-- Denominador: terremotos actuales sintéticos (event_current); una fila por marca.
SELECT flag, count(*) AS events
FROM core.event_current e
CROSS JOIN LATERAL unnest(e.quality_flags) AS flag
WHERE 'synthetic' = ANY (e.quality_flags)
GROUP BY flag
ORDER BY events DESC, flag;

-- name: completeness
-- Denominador: terremotos actuales (event_current, sin sintéticos).
SELECT count(*) AS current_earthquakes,
       count(e.magnitude) AS magnitude_not_null,
       round(100.0 * count(e.magnitude) / nullif(count(*), 0), 2) AS magnitude_pct,
       count(e.mag_type) AS mag_type_not_null,
       round(100.0 * count(e.mag_type) / nullif(count(*), 0), 2) AS mag_type_pct,
       count(e.depth_km) AS depth_km_not_null,
       round(100.0 * count(e.depth_km) / nullif(count(*), 0), 2) AS depth_km_pct,
       count(e.place) AS place_not_null,
       round(100.0 * count(e.place) / nullif(count(*), 0), 2) AS place_pct,
       count(e.country_id) AS country_id_not_null,
       round(100.0 * count(e.country_id) / nullif(count(*), 0), 2) AS country_id_pct
FROM core.event_current e
WHERE NOT ('synthetic' = ANY (e.quality_flags));

-- name: completeness-synthetic-only
-- Denominador: terremotos actuales sintéticos (event_current).
SELECT count(*) AS current_earthquakes,
       count(e.magnitude) AS magnitude_not_null,
       round(100.0 * count(e.magnitude) / nullif(count(*), 0), 2) AS magnitude_pct,
       count(e.mag_type) AS mag_type_not_null,
       round(100.0 * count(e.mag_type) / nullif(count(*), 0), 2) AS mag_type_pct,
       count(e.depth_km) AS depth_km_not_null,
       round(100.0 * count(e.depth_km) / nullif(count(*), 0), 2) AS depth_km_pct,
       count(e.place) AS place_not_null,
       round(100.0 * count(e.place) / nullif(count(*), 0), 2) AS place_pct,
       count(e.country_id) AS country_id_not_null,
       round(100.0 * count(e.country_id) / nullif(count(*), 0), 2) AS country_id_pct
FROM core.event_current e
WHERE 'synthetic' = ANY (e.quality_flags);

-- name: versions-vs-messages
-- Denominador: versiones distintas de terremotos reales frente a mensajes que añaden versión (new, revised, stale, todos los intentos).
WITH versions AS (
    SELECT count(*) AS n
    FROM core.event_version v
    JOIN core.event_current e ON e.event_id = v.event_id
    WHERE NOT ('synthetic' = ANY (e.quality_flags))
),
messages AS (
    SELECT count(*) AS n
    FROM core.message_log m
    WHERE m.outcome IN ('new', 'revised', 'stale')
      AND (m.event_id IS NULL OR m.event_id NOT LIKE 'synthetic-%')
      AND NOT EXISTS (SELECT 1 FROM core.quarantine q
                      WHERE q.kafka_topic = m.kafka_topic AND q.kafka_partition = m.kafka_partition
                        AND q.kafka_offset = m.kafka_offset AND q.is_synthetic)
      AND NOT EXISTS (SELECT 1 FROM core.event_current e
                      WHERE e.event_id = m.event_id AND 'synthetic' = ANY (e.quality_flags))
)
SELECT versions.n AS distinct_versions,
       messages.n AS version_messages,
       versions.n - messages.n AS difference
FROM versions CROSS JOIN messages;

-- name: duplicated-versions
-- Denominador: versiones distintas de terremotos reales; debe ser 0.
SELECT count(*) AS duplicated_versions
FROM (
    SELECT v.event_id, v.updated_at
    FROM core.event_version v
    JOIN core.event_current e ON e.event_id = v.event_id
    WHERE NOT ('synthetic' = ANY (e.quality_flags))
    GROUP BY v.event_id, v.updated_at
    HAVING count(*) > 1
) d;

-- name: current-uniqueness
-- Denominador: terremotos actuales (sin sintéticos); event_id repetidos en el estado actual, debe ser 0.
SELECT count(*) AS duplicated_event_ids
FROM (
    SELECT e.event_id
    FROM core.event_current e
    WHERE NOT ('synthetic' = ANY (e.quality_flags))
    GROUP BY e.event_id
    HAVING count(*) > 1
) d;

-- name: invalid-coordinates
-- Denominador: terremotos actuales (sin sintéticos); coordenadas fuera de rango, debe ser 0.
SELECT count(*) AS invalid_coordinates
FROM core.event_current e
WHERE NOT ('synthetic' = ANY (e.quality_flags))
  AND NOT (e.longitude BETWEEN -180 AND 180 AND e.latitude BETWEEN -90 AND 90);

-- name: updated-before-event
-- Denominador: terremotos actuales (sin sintéticos); updated_at anterior a event_time, debe ser 0.
SELECT count(*) AS updated_before_event
FROM core.event_current e
WHERE NOT ('synthetic' = ANY (e.quality_flags))
  AND e.updated_at < e.event_time;

-- name: country-missing-entity
-- Denominador: terremotos actuales con país asignado (sin sintéticos); país ausente de dim_country, debe ser 0.
SELECT count(*) AS missing_countries
FROM core.event_current e
WHERE NOT ('synthetic' = ANY (e.quality_flags))
  AND e.country_id IS NOT NULL
  AND NOT EXISTS (SELECT 1 FROM core.dim_country c WHERE c.country_id = e.country_id);

-- name: delays-updated-minutes
-- Denominador: terremotos actuales (sin sintéticos); minutos de ocurrencia a última actualización (mediana y p95).
SELECT count(*) AS current_earthquakes,
       percentile_cont(0.5) WITHIN GROUP (ORDER BY (extract(epoch FROM (e.updated_at - e.event_time)) / 60.0)::double precision) AS median_minutes,
       percentile_cont(0.95) WITHIN GROUP (ORDER BY (extract(epoch FROM (e.updated_at - e.event_time)) / 60.0)::double precision) AS p95_minutes
FROM core.event_current e
WHERE NOT ('synthetic' = ANY (e.quality_flags));

-- name: delays-ingested-minutes
-- Denominador: terremotos actuales (sin sintéticos); minutos de ocurrencia a primera ingesta (mediana y p95).
SELECT count(*) AS current_earthquakes,
       percentile_cont(0.5) WITHIN GROUP (ORDER BY (extract(epoch FROM (e.first_ingested_at - e.event_time)) / 60.0)::double precision) AS median_minutes,
       percentile_cont(0.95) WITHIN GROUP (ORDER BY (extract(epoch FROM (e.first_ingested_at - e.event_time)) / 60.0)::double precision) AS p95_minutes
FROM core.event_current e
WHERE NOT ('synthetic' = ANY (e.quality_flags));

-- name: excluded-events-by-type
-- Denominador: exclusiones (excluded_event, versiones de elementos que no son terremotos, sin sintéticos).
SELECT coalesce(x.event_type, '(sin tipo)') AS event_type,
       count(DISTINCT x.event_id) AS events,
       count(*) AS versions
FROM core.excluded_event x
WHERE x.event_id NOT LIKE 'synthetic-%'
GROUP BY 1
ORDER BY 1;
