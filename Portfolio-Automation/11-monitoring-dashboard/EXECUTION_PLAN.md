# Execution Plan — Monitoring & Alerting Dashboard

Source of truth: `README.md`.

## Prerequisites
- Docker + Docker Compose
- Python 3.12 (`uv`)

## Build Checklist

- [x] Compose autónomo con versiones fijas: Prometheus, Alertmanager, Grafana, Loki, Promtail, Node Exporter, Postgres Exporter y Postgres demo.
  - Verificado: `docker compose up -d --build` levanta los 10 servicios healthy en la red `monitoring_net`.
- [x] Demo App FastAPI instrumentada con métricas SLA y de negocio (`/metrics`) y logging estructurado a archivo/stdout.
  - Verificado: 13 tests unitarios pasan; métricas `http_requests_total`, `http_request_duration_seconds`, `business_processed_rows_total` y `business_active_users` exportadas en formato Prometheus.
- [x] Generador de carga simple en Python (`load_generator.py`) sin dependencias pesadas como Locust.
  - Verificado: Ejecución autónoma genera tráfico continuo hacia `/api/items`, `/api/process`, `/api/error` y `/api/slow`.
- [x] Reglas de alerta PromQL (servicio caído, tasa de errores 5xx, latencia p95, disco, Postgres caído).
  - Verificado: `promtool check rules` valida las 5 reglas sin errores.
- [x] Alertmanager configurado con webhook-sink local y Slack documentado.
  - Verificado: `amtool check-config` valida la configuración; parada de demo-app dispara alerta `ServiceDown` recibida exitosamente en `/alerts`.
- [x] Provisionamiento automático de Grafana (datasources Prometheus + Loki, dashboards de servicios y negocio).
  - Verificado: API `/api/datasources` y `/api/search` confirman ambos datasources y los dashboards `services-dashboard` y `business-dashboard`.
- [x] Recolección y consulta de logs en Loki mediante Promtail.
  - Verificado: Promtail scrapea `/var/log/demo-app/app.log`; API `/loki/api/v1/query_range` retorna los registros estructurados de demo-app.
- [x] Puertos asignados mapeados a `127.0.0.1`: Grafana 3011, Prometheus 9091, Alertmanager 9093, demo-app 8011, webhook-sink 8012, Loki 3100.
  - Verificado: Postgres y Exporters permanecen internos; ningún puerto publicado fuera de `127.0.0.1`.
- [x] Suite de pruebas automatizadas:
  - Verificado: `pytest -q` (13 passed) y `pytest -m integration -q` (6 passed).

## Definition of Done
- [x] Stack de monitoreo y servicios desplegados y verificados en Docker Compose.
- [x] Reglas de alerta y configuraciones validadas con herramientas nativas (`promtool` y `amtool`).
- [x] Prueba de ciclo completo: tráfico sintético, logs en Loki, caída de servicio, alerta despachada y recibida en webhook sink.
- [x] Documentación y planes sincronizados con la implementación real.
