# 011 · Validación de la política de tráfico (T014)

Herramienta: `gw_validate_traffic_policy` de ngrok (endpoint de agente, https, público), con el contenido de `tunnel/traffic-policy.yml`.

Esperado: política válida. Observado: `the policy is valid` (`status: valid`).

Contenido: regla `per-visitor-rate-limit` (`rate-limit` con `enforce: false`, `sliding_window`, 60 por `60s`, `bucket_key: conn.client_ip`) y regla `too-many-requests` (`expressions: actions.ngrok.rate_limit.limited`, `custom-response` 429, `content-type: application/json`, `retry-after: "60"`, cuerpo en español, sin `access-control-allow-origin`).
Límites de la cuenta: 15 reglas por política y 20 acciones por regla; se usan 2 reglas.

**Actualización (T016):** la primera versión (sin `enforce: false`) también salió «valid» pero no se comportaba como se esperaba: ngrok respondía un 429 vacío propio. La validación solo comprueba la sintaxis. Se añadió `enforce: false` y se revalidó (`the policy is valid`); ver [z9-rate-limit.md](z9-rate-limit.md).
