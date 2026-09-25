# Execution Plan — Monitoring & Alerting Dashboard

Source of truth: `README.md`. Note: only instrument/scrape services that already exist and are running — add coverage incrementally as more portfolio projects come online.

## Prerequisites
- Docker + Docker Compose
- At least one already-built FastAPI/Celery service from `01`-`09` to instrument first
- Slack webhook URL for alert testing

## Build Checklist

- [ ] Add Prometheus, Grafana, Loki, Promtail, Alertmanager to `docker-compose.yml`.
  - Verify: `docker compose up -d` → all 5 healthy; Grafana reachable on `:3000`.
- [ ] Add `prometheus-client` + `/metrics` to each already-built service (start with the furthest-along one).
  - Verify: `curl localhost:8000/metrics` returns Prometheus text format.
- [ ] Configure `node-exporter` and `postgres-exporter` for existing services.
  - Verify: both show `state: up` on Prometheus `/targets`.
- [ ] Write `prometheus.yml` scrape configs — one job per instrumented service only.
  - Verify: every configured job shows `up`.
- [ ] Provision Grafana dashboards (README section 4) for data sources that exist.
  - Verify: panels show real data, not "No data".
- [ ] Write `alert.rules.yml` (README section 5) + connect Alertmanager to Slack.
  - Verify: lowering a threshold temporarily fires a real Slack message.
- [ ] Configure Promtail → Loki log shipping. *(Promtail's last release is 3.6.11, 2026-05; Grafana's replacement is Alloy. Keep Promtail for this build; consider Alloy if Promtail stops working with the pinned Loki.)*
  - Verify: a manual test log line is queryable in Grafana Explore within seconds.
- [ ] Implement the business metrics exporter (README section 6) once a relevant service exists (e.g. invoice processor).
  - Then uncomment the `business-exporter` service and the `custom_business_metrics` scrape job in the README config.
  - Verify: `curl localhost:8001/metrics` shows non-zero business counters after real activity.
- [ ] Add `celery-exporter` pointing at the Celery broker (include the Redis password when the broker requires one, as in `10-docker-compose-lab`).
  - Verify: `celery_queue_length` appears in Prometheus (the `alert.rules.yml` queue alert depends on it).

## Definition of Done
- [ ] Every currently-built portfolio service has working `/metrics` scraped by Prometheus.
- [ ] At least one Grafana dashboard shows live, non-empty data.
- [ ] A deliberately-triggered alert reaches Slack.
- [ ] A test log line is retrievable via Loki/Grafana Explore.
- [ ] No scrape config or dashboard panel references a service that doesn't exist yet.
