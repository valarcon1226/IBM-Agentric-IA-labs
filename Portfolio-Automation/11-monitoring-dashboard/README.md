# Project: Monitoring & Alerting Dashboard

## 1. Problem Statement
Running a highly available portfolio stack requires deep visibility into service health, application performance, and business metrics. Without central observability, troubleshooting errors across distributed containers (FastAPI, Celery, Postgres, Scrapers) is slow and reactive. This project implements a comprehensive observability stack to capture logs, metrics, and trigger automated alerts based on strict SLAs.

## 2. Tech Stack
*   **Metrics Database:** Prometheus
*   **Dashboarding:** Grafana
*   **Log Aggregation:** Loki, Promtail
*   **Alerting:** Alertmanager
*   **System Metrics:** Node Exporter
*   **Database Metrics:** PostgreSQL Exporter

## 3. Architecture
```mermaid
flowchart LR
    subgraph Data Sources
        FastAPI[FastAPI Exporter]
        Celery[Celery Exporter]
        Postgres[PostgreSQL Exporter]
        Redis[Redis Exporter]
        Scrapers[Custom Python Exporters]
        Docker[Node Exporter / Promtail]
    end
    
    subgraph Observability Core
        Prometheus[Prometheus Metrics]
        Loki[Loki Logs]
        AlertManager[Alert Manager]
        Grafana[Grafana Dashboards]
    end
    
    subgraph Notifications
        Slack[Slack Webhook]
        Telegram[Telegram Bot]
        Email[SMTP]
    end

    FastAPI --> Prometheus
    Celery --> Prometheus
    Postgres --> Prometheus
    Redis --> Prometheus
    Scrapers --> Prometheus
    Docker --> Loki
    
    Prometheus --> Grafana
    Loki --> Grafana
    Prometheus --> AlertManager
    
    AlertManager --> Slack
    AlertManager --> Telegram
    AlertManager --> Email
```

## 4. File Structure
```
.
├── docker-compose.yml
├── .env.example
├── prometheus/
│   ├── prometheus.yml
│   └── alert.rules.yml
├── alertmanager/
│   └── alertmanager.yml
├── promtail/
│   └── promtail.yml
├── loki/
│   └── loki.yml
├── grafana/
│   └── provisioning/
│       ├── dashboards/
│       └── datasources/
└── exporter/
    ├── main.py
    └── requirements.txt

### `exporter/requirements.txt`
```text
prometheus-client==0.17.1
psycopg2-binary==2.9.9
```
```

## 5. Environment Variables (.env.example)
```env
# Grafana
GRAFANA_ADMIN_PASSWORD=super_secure_grafana_pass

# Custom Exporter
DATABASE_URL=postgresql://admin:password@postgres:5432/portfolio_db

# Alertmanager Settings
SLACK_WEBHOOK_URL=<your-slack-incoming-webhook-url>
TELEGRAM_BOT_TOKEN=123456789:ABCDEFGHIJKLMNOPQRSTUVWXYZ
SMTP_HOST=smtp.gmail.com
SMTP_PORT=587
SMTP_USER=alerts@example.com
SMTP_PASS=app_specific_password
```

## 6. Docker Compose Configuration (docker-compose.yml)
```yaml
version: '3.8'

networks:
  monitoring_net:
    driver: bridge

volumes:
  prometheus_data:
  grafana_data:
  loki_data:

services:
  prometheus:
    image: prom/prometheus:v3.14.0
    volumes:
      - ./prometheus/prometheus.yml:/etc/prometheus/prometheus.yml
      - ./prometheus/alert.rules.yml:/etc/prometheus/alert.rules.yml
      - prometheus_data:/prometheus
    command:
      - '--config.file=/etc/prometheus/prometheus.yml'
      - '--storage.tsdb.path=/prometheus'
      - '--web.console.libraries=/etc/prometheus/console_libraries'
      - '--web.console.templates=/etc/prometheus/consoles'
      - '--web.enable-lifecycle'
    ports:
      - "9090:9090"
    networks:
      - monitoring_net
    healthcheck:
      test: ["CMD", "wget", "-q", "--spider", "http://localhost:9090/-/healthy"]
      interval: 30s
      timeout: 10s
      retries: 3
    restart: unless-stopped

  grafana:
    image: grafana/grafana:13.2.2
    environment:
      - GF_SECURITY_ADMIN_PASSWORD=${GRAFANA_ADMIN_PASSWORD}
    volumes:
      - ./grafana/provisioning:/etc/grafana/provisioning
      - grafana_data:/var/lib/grafana
    ports:
      - "3000:3000"
    networks:
      - monitoring_net
    healthcheck:
      test: ["CMD", "wget", "-q", "--spider", "http://localhost:3000/api/health"]
      interval: 30s
      timeout: 10s
      retries: 3
    restart: unless-stopped

  loki:
    image: grafana/loki:3.7.8
    volumes:
      - ./loki/loki.yml:/etc/loki/local-config.yaml
      - loki_data:/loki
    ports:
      - "3100:3100"
    command: -config.file=/etc/loki/local-config.yaml
    networks:
      - monitoring_net
    restart: unless-stopped

  promtail:
    image: grafana/promtail:3.6.11
    volumes:
      - /var/log:/var/log
      - /var/run/docker.sock:/var/run/docker.sock:ro
      - ./promtail/promtail.yml:/etc/promtail/config.yml
    command: -config.file=/etc/promtail/config.yml
    networks:
      - monitoring_net
    restart: unless-stopped

  alertmanager:
    image: prom/alertmanager:v0.34.1
    volumes:
      - ./alertmanager/alertmanager.yml:/etc/alertmanager/alertmanager.yml
    command:
      - '--config.file=/etc/alertmanager/alertmanager.yml'
      - '--storage.path=/alertmanager'
    ports:
      - "9093:9093"
    networks:
      - monitoring_net
    restart: unless-stopped

  node-exporter:
    image: prom/node-exporter:v1.12.1
    volumes:
      - /proc:/host/proc:ro
      - /sys:/host/sys:ro
      - /:/rootfs:ro
    command:
      - '--path.procfs=/host/proc'
      - '--path.rootfs=/rootfs'
      - '--path.sysfs=/host/sys'
      - '--collector.filesystem.mount-points-exclude=^/(sys|proc|dev|host|etc)($$|/)'
    ports:
      - "9100:9100"
    networks:
      - monitoring_net
    restart: unless-stopped

  postgres-exporter:
    image: prometheuscommunity/postgres-exporter:v0.20.1
    environment:
      DATA_SOURCE_NAME: ${DATABASE_URL}
    ports:
      - "9187:9187"
    networks:
      - monitoring_net
    restart: unless-stopped

  # Enable once the business exporter (section 6) exists — see EXECUTION_PLAN.md.
  # business-exporter:
  #   build: ./exporter
  #   ports:
  #     - "8001:8001"
  #   environment:
  #     - DATABASE_URL=${DATABASE_URL}
  #   networks:
  #     - monitoring_net
  #   restart: unless-stopped

  celery-exporter:
    image: danihodovic/celery-exporter:0.12.2
    environment:
      - CELERY_BROKER_URL=redis://redis:6379/0
    ports:
      - "9808:9808"
    networks:
      - monitoring_net
    restart: unless-stopped
```

Image tags were pinned on 2026-09-24 to the newest stable tag on Docker Hub. Update them deliberately, not via `:latest`.

## 7. Metrics Monitored

| Category | Metrics |
|---|---|
| **API Performance** | Request latency (p50/p95/p99), error rate (4xx/5xx), requests/sec, endpoint breakdown |
| **Celery Workers** | Queue depth, tasks succeeded/failed/retried per hour, average task duration, worker utilization |
| **PostgreSQL** | Active connections, query duration, transactions/sec, table sizes, dead tuples |
| **Redis** | Memory usage, connected clients, hit/miss ratio, keys count |
| **Scrapers** | Pages scraped/hour, success/failure rate, average scrape time, proxy health |
| **System** | CPU %, RAM %, disk usage %, network I/O |
| **Business KPIs** | Rows processed/day, invoices extracted, leads generated, notifications sent |

## 8. Configuration Files

### `prometheus/prometheus.yml`
```yaml
global:
  scrape_interval: 15s
  evaluation_interval: 15s

rule_files:
  - "alert.rules.yml"

alerting:
  alertmanagers:
    - static_configs:
        - targets: ['alertmanager:9093']

scrape_configs:
  - job_name: 'node-exporter'
    static_configs:
      - targets: ['node-exporter:9100']

  - job_name: 'fastapi'
    metrics_path: '/metrics'
    static_configs:
      - targets: ['fastapi-gateway:8000']
      
  - job_name: 'postgres_exporter'
    static_configs:
      - targets: ['postgres-exporter:9187']

  # Enable together with the business-exporter service (section 6).
  # - job_name: 'custom_business_metrics'
  #   static_configs:
  #     - targets: ['business-exporter:8001']

  - job_name: 'celery_exporter'
    static_configs:
      - targets: ['celery-exporter:9808']
```

### `prometheus/alert.rules.yml`
```yaml
groups:
- name: portfolio_alerts
  rules:
  - alert: HighErrorRate
    expr: sum(rate(http_requests_total{status=~"5.."}[5m])) / sum(rate(http_requests_total[5m])) * 100 > 5
    for: 5m
    labels:
      severity: critical
    annotations:
      summary: High API Error Rate (5xx)
      description: API error rate is > 5% for the last 5 minutes.

  - alert: WorkerBacklog
    expr: celery_queue_length > 100
    for: 10m
    labels:
      severity: warning
    annotations:
      summary: Celery Worker Backlog
      description: Celery queue has > 100 tasks for 10 minutes.

  - alert: HighDiskUsage
    expr: (node_filesystem_size_bytes - node_filesystem_free_bytes) / node_filesystem_size_bytes * 100 > 85
    for: 10m
    labels:
      severity: warning
    annotations:
      summary: High Disk Usage
      description: Disk usage is over 85%.
```

### `alertmanager/alertmanager.yml`
```yaml
global:
  resolve_timeout: 5m
  smtp_smarthost: '${SMTP_HOST}:${SMTP_PORT}'
  smtp_from: '${SMTP_USER}'
  smtp_auth_username: '${SMTP_USER}'
  smtp_auth_password: '${SMTP_PASS}'
  smtp_require_tls: true

route:
  group_by: ['alertname']
  group_wait: 10s
  group_interval: 10m
  repeat_interval: 1h
  receiver: 'slack-notifications'
  routes:
  - match:
      severity: critical
    receiver: 'slack-notifications'
  - match:
      severity: warning
    receiver: 'email-notifications'

receivers:
- name: 'slack-notifications'
  slack_configs:
  - api_url: '${SLACK_WEBHOOK_URL}'
    channel: '#alerts'
    send_resolved: true

- name: 'email-notifications'
  email_configs:
  - to: 'admin@example.com'
    send_resolved: true
```

### `promtail/promtail.yml`
```yaml
server:
  http_listen_port: 9080
  grpc_listen_port: 0

positions:
  filename: /tmp/positions.yaml

clients:
  - url: http://loki:3100/loki/api/v1/push

scrape_configs:
- job_name: system
  static_configs:
  - targets:
      - localhost
    labels:
      job: varlogs
      __path__: /var/log/*log
- job_name: docker
  docker_sd_configs:
    - host: unix:///var/run/docker.sock
      refresh_interval: 5s
  relabel_configs:
    - source_labels: ['__meta_docker_container_name']
      regex: '/(.*)'
      target_label: 'container'
```

### `loki/loki.yml`
```yaml
auth_enabled: false

server:
  http_listen_port: 3100
  grpc_listen_port: 9096

common:
  path_prefix: /tmp/loki
  storage:
    filesystem:
      chunks_directory: /tmp/loki/chunks
      rules_directory: /tmp/loki/rules
  replication_factor: 1
  ring:
    instance_addr: 127.0.0.1
    kvstore:
      store: inmemory

schema_config:
  configs:
    - from: 2020-10-24
      store: tsdb
      object_store: filesystem
      schema: v13
      index:
        prefix: index_
        period: 24h
```

### Custom Python Exporter (Business Metrics)
```python
import os
import time
from prometheus_client import start_http_server, Gauge
import psycopg2

# Define metrics
INVOICES_TOTAL = Gauge('business_invoices_processed_total', 'Total invoices processed')
ACTIVE_USERS = Gauge('business_active_users_current', 'Current active users')

def collect_metrics():
    db_url = os.environ.get('DATABASE_URL')
    if not db_url:
        print("DATABASE_URL not set.")
        return

    try:
        conn = psycopg2.connect(db_url)
        cur = conn.cursor()
        
        cur.execute("SELECT COUNT(*) FROM invoices")
        INVOICES_TOTAL.set(cur.fetchone()[0])
        
        cur.execute("SELECT COUNT(*) FROM active_users")
        ACTIVE_USERS.set(cur.fetchone()[0])
        
        cur.close()
        conn.close()
    except Exception as e:
        print(f"Error collecting metrics: {e}")

if __name__ == '__main__':
    start_http_server(8001)
    print("Started Prometheus exporter on port 8001.")
    while True:
        collect_metrics()
        time.sleep(15)
```

## 9. Implementation Steps
1.  **Deploy core observability services:** add Prometheus, Grafana, Loki, Promtail, Node-exporter, and Alertmanager to `docker-compose.yml`. *Verify:* `docker compose up -d` brings all up healthy; Grafana UI reachable on `:3000`.
2.  **Instrument the FastAPI/Celery services that already exist:** add `prometheus-client` and expose `/metrics` on each already-built service. *Verify:* `curl localhost:8000/metrics` returns Prometheus-formatted text.
3.  **Configure infra exporters:** connect `node-exporter` and `postgres-exporter` for the services that exist. *Verify:* both targets show `state: up` in Prometheus's `/targets` page.
4.  **Wire `prometheus.yml` scrape configs:** one `job_name` per already-instrumented service. *Verify:* every configured job appears as `up` in Prometheus.
5.  **Provision Grafana dashboards:** mount the JSON dashboard definitions via volume mounts. *Verify:* opening Grafana shows real (non-empty) panels.
6.  **Configure alerting rules:** write the PromQL rules in `alert.rules.yml` and connect Alertmanager to Slack webhook. *Verify:* temporarily lowering a threshold fires a real Slack message.
7.  **Wire log routing:** configure Promtail to ship container logs to Loki. *Verify:* log line is queryable in Grafana's Explore tab (Loki data source).
8.  **Business metrics exporter:** implement the custom Python exporter. *Verify:* `curl localhost:8001/metrics` shows non-zero counts.

## 10. Testing Strategy
1.  **Metric Exposure:** `curl localhost:8000/metrics` returns Prometheus-formatted text for every instrumented service.
2.  **Load Generation:** run `locust` or `k6` against an instrumented service and confirm latency/error-rate panels update.
3.  **Alert Firing:** temporarily lower a threshold and confirm the Slack webhook actually fires.
4.  **Log Routing:** write a test log string and confirm it's queryable via Grafana's Explore tab.
