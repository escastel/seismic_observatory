# Investigación (Fase 0)

No quedan incógnitas sin resolver. Decisiones:

## R1. Origen de las cifras del análisis
- **Decisión**: `GET /api/estadisticas` y `GET /api/eventos` de la 006 con los filtros indicados; lo que
  la API no calcula (reparto por país, hora del día, profundidad) se obtiene con SQL de solo lectura
  sobre `core.event_current`, nunca sobre `replay` ni `bench`.
- **Razón**: constitución VII y decisión previa; permite regenerar cada cifra.
- **Alternativas**: recálculo en el cliente o sobre la muestra del mapa (descartado: la muestra está truncada).

## R2. Comparación equivalente
- **Decisión**: comparar últimas 24 h con la media diaria de 2025 con `min_mag=4` en ambos
  (catálogo de 2025 solo ≥ 4), denominador de 365 días incluyendo los vacíos, ND si media cero.
  Documentar también la comparación no equivalente (razón 3,87) como contraejemplo.
- **Razón**: evita el sesgo de cobertura del catálogo.
- **Alternativas**: sin filtro en ambos (imposible: 2025 no tiene M<4).

## R3. Elección de conclusiones
- **Decisión**: se eligen al ejecutar las consultas; candidatas en el spec. Se exigen ≥ 3 y se
  prefieren las que no dependen de fenómenos frágiles (reparto por país con «Sin país asignado»,
  comparación equivalente, patrón por hora UTC o profundidad por región). Se registra el instante.
- **Razón**: no prescribir conclusiones antes de ver los datos.

## R4. Operaciones a justificar y medir
- **Decisión**: (a) versiones por identificador: búsqueda secuencial sobre lista frente a diccionario
  frente a consulta sin y con clave primaria; (b) integración geográfica: punto en polígono ingenuo
  frente a índice espacial (STRtree) con los polígonos de Natural Earth; (c) agregación por ventanas
  horarias: bucle Python con diccionario frente a `GROUP BY` con `date_bin`.
- **Tamaños**: 10.000, 100.000 y 1.000.000 (mismos que la 002).
- **Medición**: tiempo con `time.perf_counter` (mediana de N repeticiones tras calentamiento),
  memoria con `tracemalloc` (pico) y, para consultas, búferes de `EXPLAIN`.
- **Razón**: son las tres operaciones que nombra el spec; la parte SQL con y sin índice ya está
  medida en la 002 y se cita, no se repite.

## R5. Latencia de la API con 1.000.000 de filas
- **Decisión**: ampliar `api_latency.py` con opción para apuntar a datos sintéticos en `bench`
  (esquema efímero de la 002, modo que no toca `core`); se mide solo lo que la 006 dejó pendiente.
  Si el equipo no soporta 1.000.000, se documenta el máximo alcanzado.
- **Alternativas**: cargar 1.000.000 en `core` (descartado: contaminaría el análisis real, principio VI).
- **Hallazgo a verificar en la implementación**: si la API solo lee `core`/`replay`, no puede leer
  `bench` sin tocar el contrato; en ese caso se mide con un esquema aislado seleccionable por la
  configuración existente del modo o se documenta como cambio justificado (FR-025). Se decide en
  la primera tarea tras mirar `api/`.

## R6. Costes
- **Decisión**: tabla por partida con columna «Medida/Supuesto»: hardware (portátil de la usuaria,
  amortización lineal), electricidad (potencia supuesta × horas × tarifa con fecha), almacenamiento
  (tamaño medido de la base y de Kafka), transferencia (bytes medidos de la API × peticiones cada
  60 s), mantenimiento y desarrollo (horas supuestas × tarifa supuesta). Límites de Netlify y ngrok
  se consultan en su documentación oficial en la fecha de redacción y se citan con fecha.
- **ROI/VAN**: el observatorio no genera ingresos; `evaluacion-financiera.md` pasa a comparar costes
  de la alternativa local frente a una operación manual **solo** si cada flujo tiene supuesto
  trazable; los flujos actuales (5.000 a 7.000 €/año) no lo tienen y se retiran o se sustituyen
  por una estimación de coste evitado con horas y tarifa explícitas, marcada como supuesto. Por
  defecto: «ROI no estimado».

## R7. Trazabilidad
- **Decisión**: una tabla por eje (§11, §12, §13) dentro de `docs/report.md`, con estado
  `superada con evidencia` / `parcial` / `pendiente (usuaria)`. Se construye leyendo los
  `README.md` de `docs/evidence/002..007`; los textos del enunciado se leen de
  `C:\Users\Casa\Downloads\resources` (el enunciado no se versiona).

## R8. Higiene
- **Decisión**: `git ls-files` filtrado por patrones (`node_modules`, `.env`, `*.bak`, `*.orig`, datos
  en `data/`, volúmenes) y búsqueda de secretos con patrones comunes en ficheros versionados, sin
  imprimir `.env`. Reescritura de historia solo con confirmación.

## R9. Orquestación
- Sesión principal: mediciones, cifras, conclusiones, matrices. Haiku: tablas y redacción mecánica
  desde evidencia; Sonnet: el script de medición y su prueba. Sin solapamiento de ficheros.
