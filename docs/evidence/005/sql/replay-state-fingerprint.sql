-- Huella del estado de replay: recuento y suma de comprobación del contenido de cada evento actual.
-- replayed_at se excluye a propósito: cambia en cada reproducción; el resto no debe cambiar.
SELECT count(*) AS events,
       coalesce(sum(hashtextextended(event_id || '|' || event_time::text || '|' || updated_at::text || '|'
                    || coalesce(magnitude::text, '') || '|' || coalesce(country_id, '') || '|'
                    || array_to_string(quality_flags, ','), 0)::numeric), 0) AS checksum
FROM replay.event_current;
