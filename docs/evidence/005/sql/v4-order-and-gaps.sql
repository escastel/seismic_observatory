-- V4: tras pausar, reanudar y detener no hay saltos, repeticiones ni desorden.
-- Los desplazamientos (offsets) de Kafka no empiezan en 0 si el topic ya se usó antes: se mide la contigüidad.
WITH log AS (
    SELECT m.kafka_offset, v.event_time,
           lag(v.event_time) OVER (ORDER BY m.kafka_offset) AS previous_time,
           lag(m.kafka_offset) OVER (ORDER BY m.kafka_offset) AS previous_offset
    FROM replay.message_log m
    JOIN replay.event_version v ON v.event_id = m.event_id AND v.updated_at = m.updated_at
    WHERE m.kafka_topic = 'earthquakes.replay'
)
SELECT count(*)                                              AS messages,
       count(*) = count(DISTINCT kafka_offset)               AS no_repeated_offsets,
       max(kafka_offset) - min(kafka_offset) + 1 = count(*)  AS no_gaps,
       count(*) FILTER (WHERE event_time < previous_time)    AS out_of_time_order
FROM log;
SELECT (SELECT count(*) FROM replay.event_current) AS replay_events,
       (SELECT count(*) FROM replay.message_log WHERE outcome = 'new') AS new_messages;
