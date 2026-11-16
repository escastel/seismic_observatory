---
name: verify-stack
description: Levanta el stack de Docker Compose del observatorio, espera a las comprobaciones de salud, ejecuta las pruebas en el contenedor `tests` y los escenarios del quickstart de la feature, y guarda la evidencia (esperado, observado, salida) en docs/evidence/NNN/. Úsala siempre que haya que comprobar un cambio con el sistema real, validar un escenario V1–V12 de un quickstart, cerrar una tarea que pida evidencia, ejecutar pytest de tests/db o medir arranques e índices. También cuando se pregunte si algo "funciona", "pasa" o "está verificado".
---

# verify-stack

La constitución (principio IX y «Flujo de Desarrollo y Calidad») exige que todo cambio en
consumidor, modelo, servicios, contratos o analítica se compruebe con el stack levantado, y que
una prueba solo se declare superada **después de ejecutarla** y guardar resultado esperado,
resultado observado y evidencia repetible. Esta skill fija cómo se hace en este repositorio, en
Windows (Git Bash) y en Linux.

## Reglas que no se negocian

1. **Nunca mostrar secretos.** No leer ni imprimir `.env`. No ejecutar `docker compose config`
   (vuelca las contraseñas resueltas). Para comparar variables, comparar solo los nombres.
2. **`docker compose down -v` borra la base local**: pedir confirmación explícita cada vez,
   aunque una tarea lo indique (T013 y T041 lo marcan como «requiere confirmación»).
3. **No dar nada por superado sin ejecutarlo.** Si un paso no se pudo ejecutar (Docker parado,
   servicio aún no implementado), la evidencia dice «NO EJECUTADA» y por qué.
4. **Las variables de PostgreSQL se expanden dentro del contenedor**, no en el equipo:
   `docker compose exec -T postgres sh -c 'psql -U "$POSTGRES_USER" -d "$POSTGRES_DB" ...'`.
   Las órdenes del quickstart que usan `"$POSTGRES_USER"` en el equipo se adaptan así.
5. **En Windows** se usa Git Bash. Si una orden pasa rutas absolutas de contenedor como
   argumento (`/sql`, `/catalog/...`), anteponer `MSYS_NO_PATHCONV=1` para que MSYS no las
   convierta en rutas de Windows.
6. No parar el stack al terminar salvo que se pida: otras comprobaciones pueden necesitarlo.

## Paso 0. Precondiciones

```bash
docker info --format '{{.ServerVersion}}' >/dev/null 2>&1 || echo "Docker no responde"
git check-ignore -q .env && echo ".env ignorado" || echo "ATENCIÓN: .env no existe o no está ignorado"
# Variables de .env.example que faltan en .env (solo nombres, nunca valores):
comm -23 <(grep -oE '^[A-Z0-9_]+=' .env.example | sort -u) <(grep -oE '^[A-Z0-9_]+=' .env | sort -u)
```

- Si Docker no responde, pedir que se arranque Docker Desktop (Windows) o el servicio `docker`
  (Linux). No continuar.
- Si faltan variables, decir cuáles y parar: completar `.env` es tarea de la usuaria.
- La feature activa sale de `.specify/feature.json` (`specs/NNN-...`); su número `NNN` es la
  carpeta de evidencias.

## Paso 1. Levantar y esperar la salud

```bash
SECONDS=0
docker compose up --build -d --wait --wait-timeout 300; status=$?
echo "exit=$status tiempo=${SECONDS}s"
```

`--wait` espera a que cada servicio esté `healthy` (o `running` si no declara comprobación).
Para medir el criterio de la spec (tres minutos con imágenes ya construidas) repetir sin
`--build`.

Si falla:

```bash
docker compose ps -a --format 'table {{.Service}}\t{{.State}}\t{{.Status}}'
docker compose logs --tail 100 <servicio> | grep -vi password
```

Diagnosticar desde los logs antes de reintentar. Revisar que los logs no contengan secretos
antes de citarlos. `--wait` termina en cuanto un servicio queda `unhealthy`: un servicio en
`Restarting` es un bucle de fallos, pararlo con `docker compose stop <servicio>` antes de seguir.

Causa conocida al alternar de equipo: el volumen `postgres_data` es local a cada máquina. Si
el log dice `database files are incompatible with server` o la estructura no coincide con
`db/sql/`, ese volumen es de un modelo anterior: los ficheros de inicialización solo se aplican
con el volumen vacío. Se arregla con `docker compose down -v` (regla 2: confirmar antes).

## Paso 2. Estado y superficie expuesta

```bash
docker compose ps --format 'table {{.Service}}\t{{.State}}\t{{.Status}}\t{{.Ports}}'
```

La salud va dentro de `Status`, por ejemplo `Up 2 minutes (healthy)`; Compose no tiene un
campo `Health` en este formato.

Comprobar contra la constitución (principio I) y `specs/NNN/contracts/runtime.md`:

- cinco servicios obligatorios: `postgres`, `kafka`, `producer`, `consumer`, `api`;
- solo `api` publica puerto, y en `127.0.0.1`; ni Kafka ni PostgreSQL;
- un servicio cuyo `Status` no lleva `(healthy)` ni `(unhealthy)` **no tiene comprobación de
  salud**: informarlo como tal, nunca como «sano».

Mientras la 002 no termine T035, Kafka publica puertos y los servicios Python no declaran
salud: es una desviación conocida, se registra como FALLIDA con esa nota, no se oculta.

## Paso 3. Pruebas en el contenedor `tests`

Las pruebas se ejecutan dentro de la red de Compose (las bases y el broker no se publican):

```bash
mkdir -p docs/evidence/NNN
docker compose -f compose.yaml -f compose.dev.yaml run --rm tests pytest <ruta> -v 2>&1 \
  | tee docs/evidence/NNN/<fichero>.txt
echo "pytest exit=${PIPESTATUS[0]}"
```

- `<ruta>`: la que pida la tarea (`tests/db`, `tests/unit/...`). Sin indicación, `tests/db`.
- El contenedor monta el repositorio en solo lectura salvo `docs/evidence/`, así que una prueba
  que intente escribir fuera falla: es intencionado.
- El código de salida de pytest decide el resultado, no la lectura del texto.

## Paso 4. Escenarios del quickstart

Leer `specs/NNN/quickstart.md` y ejecutar los escenarios pedidos (V1…Vn) tal como están,
aplicando las reglas 4 y 5. Para cada uno, anotar la orden exacta, el resultado esperado
copiado del quickstart y lo observado. Los escenarios que dependen de algo aún no implementado
se registran como NO EJECUTADA con la tarea que lo cerrará.

Escenarios que piden confirmación o acción de la usuaria:

- arranques desde cero (V1 repetido) y persistencia: usan `down -v` → regla 2;
- prueba de puertos «desde otro dispositivo» (V2): pedir a la usuaria que la haga y anotar lo
  que informe, indicando que es una observación suya;
- túnel (V10): requiere `NGROK_AUTHTOKEN` y `NGROK_DOMAIN` en `.env`; comprobar solo que existen
  por nombre.

## Paso 5. Guardar la evidencia

Ubicación: `docs/evidence/NNN/`. Nombres en inglés (constitución, «Idioma»). Si la tarea fija un
nombre (`db-tests.txt`, `startup.md`, `repository-hygiene.txt`), usar ese; si no,
`v<n>-<slug>.md`.

Cabecera de cada fichero Markdown, generada con el script:

```bash
bash .claude/skills/verify-stack/scripts/evidence-header.sh
```

Plantilla (documentación en español):

```markdown
# V4 · Secuencia de duplicados y revisiones

<salida de evidence-header.sh>

| | |
|---|---|
| Escenario | V4 (US2 · SC-003), specs/NNN/quickstart.md |
| Orden | `docker compose -f compose.yaml -f compose.dev.yaml run --rm tests pytest tests/db -v` |
| Esperado | … (copiado del quickstart) |
| Observado | … (cifras reales) |
| Resultado | SUPERADA · FALLIDA · NO EJECUTADA |

## Salida

<salida relevante, o referencia al .txt con la salida completa>
```

Antes de dar la evidencia por guardada, comprobar que no contiene secretos de `.env`:

```bash
bash .claude/skills/verify-stack/scripts/scan-evidence.sh docs/evidence/NNN
```

Si informa de alguna fuga, sustituir el valor por `***` en el fichero y volver a comprobar.

## Paso 6. Informe

Responder con una tabla escenario · esperado · observado · resultado y la ruta de cada fichero
de evidencia. Las FALLIDAS van primero, con la causa y la tarea o el cambio que la resolvería.
Si alguna tarea de `tasks.md` queda cumplida por la evidencia, decirlo, pero marcarla `[X]`
solo cuando lo haga el flujo de `speckit-implement` o lo pida la usuaria.
