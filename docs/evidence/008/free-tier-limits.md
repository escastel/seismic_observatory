# Límites de las cuotas gratuitas (T018)

**Consultado**: 2026-11-17. Una cuota gratuita no es coste cero: es un coste cubierto por el proveedor hasta un tope, y al
superarlo el servicio se corta o pasa a pagarse.

## ngrok (plan gratuito) — medido en la cuenta con el conector de ngrok

| Límite | Valor | Uso observado (nov-2026) | Al superarlo |
|---|---|---|---|
| Transferencia de salida al mes (`OutgoingTrafficPerMonth`) | 1.000.000.000 bytes (1 GB) | 191.053.586 bytes (19 %) | el túnel deja de servir tráfico hasta el mes siguiente o hasta mejorar de plan (error `ERR_NGROK_725`) |
| Conexiones HTTP por minuto | 4.000 | muy por debajo | rechazo con `ERR_NGROK_734` |
| Conexiones simultáneas a endpoints | 100 | 1 | `ERR_NGROK_714` |
| Endpoints concurrentes | 3 | 1 | `ERR_NGROK_18021` |
| Sesiones de agente simultáneas | 3 | 1 | `ERR_NGROK_108` |
| Retención del inspector de tráfico | 1 día | — | los detalles de petición más antiguos no están disponibles |
| Peticiones HTTP al mes | ilimitadas | 5.282 | — |

**Consecuencia**: con el panel abierto de forma continua (≈ 89 MB/día, ver [cost-measurements.md](cost-measurements.md)) el
tope de 1 GB se alcanzaría en unos 11 días; con el uso real de este mes (≈ 11 MB/día) no se alcanza. En la defensa el
túnel está abierto unas horas, pero un panel olvidado abierto puede agotarlo. Mitigación sin coste: el refresco ya es de 60 s
(el mínimo del enunciado) y las peticiones de la ventana por defecto son pequeñas; no se añade compresión porque la API
no la tiene (cambio fuera de alcance).

## Netlify (plan gratuito) — fuente: documentación pública de Netlify

Fuentes: <https://docs.netlify.com/manage/accounts-and-billing/billing/billing-for-credit-based-plans/credit-based-pricing-plans/>
y <https://www.netlify.com/pricing/>, consultadas el 2026-11-17 mediante búsqueda; **no se ha comprobado el panel de la
cuenta**, y las fuentes discrepan en algunas tarifas.

| Límite (plan gratuito con créditos) | Valor publicado | Al superarlo |
|---|---|---|
| Créditos al mes | 300, límite duro, sin recarga automática | los proyectos se pausan hasta el siguiente ciclo de facturación |
| Ancho de banda | 20 créditos por GB (el changelog de 2025 decía 10) | consume créditos |
| Peticiones web | 2 créditos por 10.000 | consume créditos |
| Despliegue a producción | 15 créditos cada uno; previews y despliegues de rama: 0 | consume créditos |
| Compilaciones concurrentes | 1 | las demás esperan |
| Cuentas anteriores al 4-sep-2025 (plan «legacy») | 100 GB/mes de ancho de banda y 300 minutos de compilación, límites duros | corte hasta el mes siguiente |

**Estimación (supuesto, con las tarifas de arriba)**: la SPA pesa ≈ 1,2 MB; 1.000 visitas serían ≈ 1,2 GB ≈ 24 créditos de
ancho de banda (más unos pocos créditos de peticiones), más 15 por cada despliegue: la cuota (300 créditos) sobra para una defensa.
Los datos del panel no pasan por Netlify, sino por ngrok.
