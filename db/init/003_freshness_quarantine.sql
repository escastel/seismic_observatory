ALTER TABLE cuarentena
    DROP CONSTRAINT IF EXISTS cuarentena_quality_dimension_check;

ALTER TABLE cuarentena
    ADD CONSTRAINT cuarentena_quality_dimension_check
    CHECK (
        quality_dimension IN (
            'Completitud',
            'Validez',
            'Exactitud',
            'Consistencia',
            'Oportunidad',
            'Unicidad',
            'Frescura'
        )
    );
