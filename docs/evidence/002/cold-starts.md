# Arranques desde cero (V1 repetido, SC-002)

- Observado (UTC): 2026-11-15T00:47:33Z
- Rama y commit: 002-platform-data-model @ a0eb6e1 (con cambios sin commit)
- Equipo: MINGW64_NT-10.0-26200 3.5.4-cbe555e0.x86_64 x86_64
- Motor: Docker 29.1.3 (Docker Desktop (containerized)), Compose 2.40.3-desktop.1; recursos del motor: 12 CPU, 7.6 GiB
- Orden: `bash tests/startup/cold_start.sh 10`

Imágenes construidas una vez antes de medir. Cada arranque: `docker compose down -v`,
`docker compose up -d` y espera, consultando `docker compose ps` cada segundo, hasta que
los cinco servicios (postgres kafka producer consumer api) están `healthy`.

| Arranque | Tiempo hasta cinco servicios sanos (s) |
|---:|---:|
| 1 | 21,3 |
| 2 | 22,1 |
| 3 | 22,1 |
| 4 | 22,4 |
| 5 | 15,5 |
| 6 | 15,7 |
| 7 | 15,7 |
| 8 | 15,8 |
| 9 | 15,2 |
| 10 | 15,3 |

| Mínimo | Mediana | Máximo | Por encima de 180 s |
|---:|---:|---:|---:|
| 15,2 | 15,7 | 22,4 | 0 de 10 |

Resultado: SUPERADA. Los 10 arranques quedan por debajo de 180 s.
