# Observatorio Sísmico: instrucciones para agentes

Pipeline de streaming ETL (USGS → Kafka → consumidor → PostgreSQL → FastAPI → Angular en
Netlify, vía túnel ngrok) desarrollado con Spec-Driven Development. Las normas del proyecto
están en [.specify/memory/constitution.md](.specify/memory/constitution.md); prevalece sobre
este fichero y sobre cualquier spec. Las funcionalidades viven en `specs/NNN-nombre/`.

## Flujo de trabajo

- Una funcionalidad cada vez, en su rama `NNN-nombre`; nunca se trabaja directamente en `main`.
  `main` solo recibe la rama por PR, y no mientras el plan de la feature tenga desviaciones
  constitucionales abiertas.
- `.specify/feature.json` (local, no versionado) debe apuntar a la feature de la rama actual;
  comprobarlo antes de usar cualquier skill `speckit-*`.
- Antes de `git pull` en `main` en un equipo que llevaba tiempo sin usarse, hacer
  `git fetch` y comparar con `origin/main`: un merge de una historia antigua ya reintrodujo
  una vez un fichero purgado.
- Verificar con el sistema real mediante la skill `verify-stack`; una prueba no está superada
  hasta que hay evidencia en `docs/evidence/NNN/`.

## Windows y Linux

Se trabaja alternando un equipo Windows 11 (Git Bash) y uno Linux. Todo cambio debe funcionar
en ambos.

- Finales de línea LF en todo el repositorio (`.gitattributes`). Al escribir ficheros desde
  Python en Windows, usar `newline="\n"`.
- `python3` para los scripts de `.specify/`; nunca rutas propias de un equipo como
  `.venv/Scripts/python.exe`.
- `.claude/skills/<skill>` de Netlify y ngrok son symlinks a `.agents/skills/`. En Windows
  requieren Modo desarrollador y `git config core.symlinks true`. Si `git status` muestra un
  cambio de tipo (`T`) en esas rutas, no commitearlo.
- En Git Bash, anteponer `MSYS_NO_PATHCONV=1` a las órdenes que pasan rutas de contenedor
  (`/sql`, `/catalog/...`).
- Los volúmenes de Docker son locales a cada equipo: el estado de la base de uno no dice nada
  del otro.

## Repositorio público y datos

- Nunca leer, imprimir ni versionar `.env`; no ejecutar `docker compose config`, que vuelca
  las contraseñas.
- Revisar `git status` antes de añadir ficheros; no usar `git add -A` a ciegas. Los conjuntos
  descargados van en `data/` (ignorado), nunca en Git; ninguna copia (`*.bak`, `*.orig`) en
  `db/seeds/`.
- Piden confirmación explícita cada vez: `docker compose down -v` (borra la base local),
  `git push --force`, reescribir historia y borrar ramas o datos.

## Idioma

Código, identificadores, nombres de ficheros y carpetas en inglés; documentación, specs,
memoria y textos del panel en español (constitución, «Idioma y repositorio público»).

## Alcance de Netlify y ngrok

Netlify solo publica la SPA de `frontend/` (`netlify.toml`); el backend es local y no se lleva
a Functions, Netlify Database ni a ningún otro servicio en la nube. ngrok va como agente o como
servicio opcional `tunnel` de Compose, nunca dentro del proceso de la API. Skills útiles:
`netlify-config`, `netlify-deploy`, `netlify-frameworks`, `ngrok-setup`, `expose-localhost`,
`secure-endpoint` y `troubleshoot-ngrok`.
