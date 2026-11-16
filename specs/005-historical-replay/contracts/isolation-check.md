# Contrato: comprobación de aislamiento de `core`

Demuestra, con datos y no con inspección del código, que una reproducción no altera los datos
reales (principio VI, FR-013, SC-003).

## Procedimiento

1. Parar el productor en vivo: `docker compose stop producer`. El feed real escribe en `core` por
   su cuenta y falsearía la comparación. El consumidor puede seguir en marcha.
2. Esperar a que el consumidor esté al día (retraso 0 en el grupo de `earthquakes.live` y
   `earthquakes.catalog`).
3. `docker compose run --rm replay snapshot`.
4. Ejecutar la reproducción (`start`, o `start --synthetic-only`) hasta que termine y el consumidor
   esté al día en `earthquakes.replay`.
5. `docker compose run --rm replay compare`.
6. Repetir con `reset` y una nueva reproducción; comparar otra vez.
7. Reanudar el productor: `docker compose start producer`.

## Qué se mide

Para **cada tabla del esquema `core`** (descubierta en el catálogo de PostgreSQL, de modo que una
tabla nueva se incluye sola):

```sql
SELECT count(*) AS rows,
       coalesce(sum(hashtextextended(t::text, 0)::numeric), 0) AS checksum
FROM core.<tabla> AS t;
```

En `core.extraction` se añade `WHERE purpose <> 'replay_selection'`: la fila de cada selección es
la constancia que exige la spec y es la única diferencia admitida (R5). El resultado de la
comparación lista además, aparte, cuántas filas `replay_selection` hay.

## Salida de `compare`

```text
core.dim_country        177  ==  177   checksum igual
core.event_current    33021  ==  33021  checksum igual
…
core.extraction            N  ==  N    checksum igual (sin contar replay_selection: M filas)
Aislamiento: correcto, 0 tablas con diferencias
```

Código de salida 0 si todas las tablas coinciden y 6 si no. Si difieren, se imprime la tabla, los
dos recuentos y las dos sumas.

## Limitaciones declaradas

- La suma de comprobación detecta cualquier cambio de contenido de fila con probabilidad de colisión
  despreciable para este tamaño, pero no es una prueba criptográfica; basta para detectar una
  escritura accidental.
- La comprobación solo es válida con el productor en vivo parado. La evidencia lo registra.
- Compara el estado de `core`, no demuestra por sí sola que no se leyó de él; la lectura de `core`
  por el consumidor (para país y dimensiones) es legítima y no la altera.
