# 012 · Botón de tema arriba a la izquierda y retoques de documentación

Rama `012-theme-toggle-left-and-doc-fixes`, desde `main` tras el PR #12. Sin cambios en la API, la base de datos ni el contrato.

## Botón flotante de tema (panel)

Cambio: el botón fijo de claro/oscuro pasa de la esquina superior derecha a la **superior izquierda** (`frontend/src/app/theme-toggle/theme-toggle.component.css`: `left` en lugar de `right`). Como el logo y el título quedan en la misma esquina, la cabecera se desplaza 60 px a la derecha en pantallas de hasta 1280 px (`frontend/src/app/app.component.css`) para que el botón no los tape.

Comprobación: Chrome (Puppeteer) contra `ng serve` con `config.json` temporalmente apuntando a la API local (restaurado después; `git diff` vacío). Datos en [toggle-report.json](toggle-report.json).

| Ancho | Esquema | Esperado | Observado |
|---|---|---|---|
| 1366 | claro y oscuro | botón en (16, 16), 48 px, sin solapar logo, título ni zoom del mapa | (16, 16), 48 px, sin solapes ([captura](toggle-1366-light.png)) |
| 768 | claro y oscuro | igual | sin solapes ([captura](toggle-768-dark.png)) |
| 375 | claro y oscuro | igual | sin solapes ([claro](toggle-375-light.png), [oscuro](toggle-375-dark.png)) |
| Todos | clic en el botón | cambia el tema | cambia de claro a oscuro y de oscuro a claro en los seis casos |

Antes de la corrección de la cabecera, el botón sí tapaba el logo y el título a 768 y 375 px (comprobado con la misma prueba).

Pruebas: `vitest run` 199 en verde (18 ficheros); `ng build` compila. **No comprobado**: el panel ya desplegado en Netlify (se publica al hacer merge) ni otro dispositivo.

## Documentación

- `.env.example`: añadida `API_MAX_FEATURES` (se usaba en `compose.yaml` con valor por defecto 1000).
- `docs/report.md`: el índice incluye «Ajustes del panel (spec 010)» y la introducción dice «specs 002 a 011».
- La prueba en Linux deja de figurar como pendiente: queda fuera de alcance por decisión de la persona autora (no es requisito del enunciado). Se actualizaron `docs/report.md`, `README.md` y los README de evidencias 007, 009, 010 y 011. La comprobación de la spec 008 (G3, 886 pruebas) se conserva como estaba.
