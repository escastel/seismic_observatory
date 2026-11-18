# X12. Botón de tema (T028–T030)

Sistema real (API local, `ng serve`, Chrome con Puppeteer; cada caso en un contexto de navegador limpio). Datos en [x12-theme-toggle.json](x12-theme-toggle.json); capturas `x12-*.png`.

| Comprobación | Esperado | Observado |
|---|---|---|
| Dispositivo oscuro, sin elección guardada | oscuro, sin `data-theme`, botón «Cambiar a tema claro» | fondo `rgb(11,21,32)`, `data-theme` ausente, etiqueta correcta |
| Pulsar el botón | claro sin recargar, misma lectura, sin peticiones nuevas | fondo `rgb(238,243,246)`, `data-theme="light"`, `localStorage` = `light`, etiqueta «Cambiar a tema oscuro», 0 peticiones `/api/` durante el cambio, mismo recuento (194 eventos dibujados, barra 194); mapa y gráficos pasan a claro (`x12-2-…`, `x12-4-…`) |
| `theme-color` | sigue al tema elegido | ambas metas `#eef3f6` |
| Recargar | conserva la elección aunque el dispositivo sea oscuro | claro, etiqueta «Cambiar a tema oscuro» |
| Cambio del dispositivo con elección manual | se ignora | sigue claro |
| Sin elección: seguir al dispositivo | claro y, al cambiar a oscuro, oscuro en vivo | `rgb(238,243,246)` → `rgb(11,21,32)` |
| `localStorage` bloqueado | el tema cambia igualmente | `rgb(11,21,32)` → `rgb(238,243,246)`, `data-theme="light"` |
| Teclado | foco visible, Enter y Espacio alternan, tamaño táctil ≥ 44 px | contorno sólido de 3 px, 48×48 px; Enter → oscuro, Espacio → claro |
| «Reducir movimiento» | sin transición | `transition-duration` y `animation-duration` 0 s |

**No comprobado**: el anuncio con un lector de pantalla real; solo la etiqueta accesible del botón y que sea un `<button>` operable por teclado.
