# 011 · Recursos externos, CSP y accesibilidad de `/docs` (T020: Z11 y Z12)

Navegador: Chrome (Puppeteer) contra `http://127.0.0.1:8000/docs`; axe-core con las reglas WCAG 2 A y AA. Datos en [z11-z12-report.json](z11-z12-report.json).

## Z11 · Recursos y CSP

| Comprobación | Esperado | Observado |
|---|---|---|
| Recursos con versión exacta e `integrity` | `swagger-ui-dist@5.17.14`, `sha384-…`, `crossorigin="anonymous"` | CSS y JS desde `cdn.jsdelivr.net/npm/swagger-ui-dist@5.17.14/` con los `sha384` del contrato y `crossorigin: anonymous` |
| Dominios externos | solo `cdn.jsdelivr.net` | `127.0.0.1:8000` y `cdn.jsdelivr.net` (en ambos esquemas de color) |
| Cabecera CSP | la del contrato | `default-src 'none'; script-src 'self' https://cdn.jsdelivr.net 'unsafe-inline'; style-src 'self' https://cdn.jsdelivr.net 'unsafe-inline'; img-src 'self' data: https://cdn.jsdelivr.net; connect-src 'self'` |
| `integrity` alterado impide cargar el script | el navegador lo rechaza | con un carácter cambiado en el hash del JS: `SwaggerUIBundle` sin definir, 0 operaciones dibujadas, consola «Failed to find a valid digest in the 'integrity' attribute…» ([captura](z11-tampered-integrity.png)) |

Nota: la CSP incluye `'unsafe-inline'` en scripts y estilos porque la página inicializa Swagger con un bloque en línea; es una concesión consciente del contrato, no un descuido. La consola solo registra un 404 (atribuido a `/favicon.ico`, no comprobado petición a petición).

## Z12 · Accesibilidad (axe-core, WCAG A y AA)

| Vista | Violaciones | Detalle |
|---|---|---|
| `/docs` cerrada | 2 (grave) | `color-contrast` (6 nodos, etiquetas y bloques de la interfaz de Swagger), `nested-interactive` (3 nodos, controles de cada operación) |
| `/docs` con `/api/eventos` abierta | 3 | las dos anteriores (18 nodos de contraste) y `select-name` (crítica, 1 nodo: el selector de tipo de contenido de Swagger, `.parameters-col_description > select`) |

Todos los nodos señalados pertenecen a la interfaz de Swagger UI 5.17.14 (clases `.opblock-*`, `.parameters-col_*`, `.version`); el aviso de recursos externos y el título de la página, que son nuestros, no aparecen entre las violaciones. **Se aceptan como excepciones atribuibles a Swagger UI**: no se parchea una librería de terceros con integridad fijada. **No cumple al 100 % WCAG AA**; queda anotado en el informe como limitación conocida.

## Esquema de color

Capturas [clara](z11-docs-light.png) y [oscura](z11-docs-dark.png) con `prefers-color-scheme`: Swagger UI no tiene tema oscuro y la página es idéntica en ambos casos (fondo claro). No se adaptó al tema oscuro; limitación conocida.
