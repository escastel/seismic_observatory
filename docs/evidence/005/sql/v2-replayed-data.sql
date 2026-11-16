-- V2 y V8: lo reproducido está solo en el esquema replay y es identificable como tal.
\echo '== eventos distintos y versiones en replay'
SELECT (SELECT count(*) FROM replay.event_current)  AS event_current,
       (SELECT count(*) FROM replay.event_version)  AS event_version,
       (SELECT count(*) FROM replay.quarantine)     AS quarantine,
       (SELECT count(*) FROM replay.excluded_event) AS excluded;

\echo '== identificabilidad: sin replayed_at nulo, todo viene del topic de reproducción'
SELECT count(*) FILTER (WHERE replayed_at IS NULL) AS without_replayed_at,
       min(replayed_at) AS first_replayed_at,
       max(replayed_at) AS last_replayed_at
FROM replay.event_current;
SELECT kafka_topic, count(*) FROM replay.event_version GROUP BY kafka_topic;
SELECT kafka_topic, outcome, count(*) FROM replay.message_log GROUP BY 1, 2 ORDER BY 1, 2;

\echo '== core no recibió nada de la reproducción (replayed_at siempre nulo en core)'
SELECT count(*) FILTER (WHERE replayed_at IS NOT NULL) AS core_rows_with_replayed_at FROM core.event_current;
SELECT count(*) AS core_versions_from_replay_topic FROM core.event_version WHERE kafka_topic = 'earthquakes.replay';

\echo '== el mismo identificador en core y en replay (valores propios en cada esquema)'
SELECT c.event_id,
       c.magnitude AS core_magnitude, r.magnitude AS replay_magnitude,
       c.event_time = r.event_time AS same_event_time,
       c.replayed_at IS NULL AS core_not_replayed, r.replayed_at IS NOT NULL AS replay_is_replayed
FROM core.event_current c JOIN replay.event_current r USING (event_id)
ORDER BY c.event_id LIMIT 5;
SELECT count(*) AS ids_in_both_schemas FROM core.event_current c JOIN replay.event_current r USING (event_id);
