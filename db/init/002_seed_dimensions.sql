INSERT INTO dim_geografia (
    country,
    continent,
    subregion,
    source_dataset,
    geometry_hash
)
VALUES (
    'Sin país asignado',
    'Sin continente asignado',
    'Sin subregión asignada',
    'Natural Earth',
    'maritime-default'
)
ON CONFLICT (
    country,
    continent,
    subregion,
    source_dataset,
    geometry_hash
) DO NOTHING;
