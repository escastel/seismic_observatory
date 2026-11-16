-- V1: cada selección de reproducción queda registrada en core.extraction con sus parámetros.
SELECT extraction_id,
       purpose,
       request_url,
       outcome,
       window_start::date AS window_start,
       window_end::date   AS window_end,
       record_count,
       earthquake_count,
       published_count,
       request_params->>'min_magnitude' AS min_magnitude,
       request_params->>'bbox'          AS bbox,
       jsonb_array_length(request_params->'files') AS files
FROM core.extraction
WHERE purpose = 'replay_selection'
ORDER BY extraction_id;
