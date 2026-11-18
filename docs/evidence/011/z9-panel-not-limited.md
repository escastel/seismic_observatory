# 011 · El uso normal del panel no se limita (T017)

Prueba: panel de Netlify (`https://seismicobservatoryecr.netlify.app/`, configuración real, a través del túnel con la política activa) abierto 5 minutos (14:43:28 a 14:48:32 UTC) en Chrome (Puppeteer), con su refresco automático de 60 s. Captura: [z9-panel.png](z9-panel.png).

| Comprobación | Esperado | Observado |
|---|---|---|
| Respuestas 429 | ninguna | ninguna: inspector de ngrok (14:43:20–14:48:40) → 37 × 200 y nada más |
| Peticiones del navegador a la API | por debajo de 60 por minuto | 21 respuestas, todas 200 (carga inicial duplicada = 6 en el segundo 2, y 3 por minuto después: `/api/eventos`, `/api/salud`, `/api/estadisticas`) |
| Máximo por minuto visto por ngrok | muy por debajo de 60 | 10 (14:43), luego 6, 7, 6, 6 y 3 |
| Errores de página | ninguno | ninguno |

Nota: ngrok cuenta 37 peticiones frente a las 21 que vio el navegador (probablemente peticiones previas de comprobación CORS `OPTIONS`; no verificado). Aun así, el máximo es 10 por minuto, 6 veces menos que el límite de 60.
