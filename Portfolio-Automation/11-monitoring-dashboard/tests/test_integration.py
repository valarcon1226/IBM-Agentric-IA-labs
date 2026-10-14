import time

import httpx
import pytest


@pytest.mark.integration
def test_all_prometheus_targets_up():
    """Verify that all targets configured in Prometheus have health == 'up'."""
    url = "http://127.0.0.1:9091/api/v1/targets"
    # Wait up to 30s for all targets to be scraped and reported up
    targets_up = False
    last_status = {}
    for _ in range(15):
        try:
            resp = httpx.get(url, timeout=5.0)
            if resp.status_code == 200:
                data = resp.json()
                active_targets = data.get("data", {}).get("activeTargets", [])
                last_status = {
                    t.get("labels", {}).get("job"): t.get("health") for t in active_targets
                }
                if active_targets and all(t.get("health") == "up" for t in active_targets):
                    targets_up = True
                    break
        except Exception:
            pass
        time.sleep(2)

    assert targets_up, f"Not all Prometheus targets are up: {last_status}"


@pytest.mark.integration
def test_prometheus_alert_rules_loaded():
    """Verify that Prometheus has loaded all 5 required alert rules."""
    url = "http://127.0.0.1:9091/api/v1/rules"
    resp = httpx.get(url, timeout=5.0)
    assert resp.status_code == 200
    data = resp.json()
    rule_groups = data.get("data", {}).get("groups", [])
    assert len(rule_groups) > 0

    rule_names = {r.get("name") for g in rule_groups for r in g.get("rules", [])}
    expected_rules = {
        "ServiceDown",
        "HighErrorRate5xx",
        "HighLatencyP95",
        "HighDiskUsage",
        "PostgresDown",
    }
    assert expected_rules.issubset(rule_names), f"Missing rules: {expected_rules - rule_names}"


@pytest.mark.integration
def test_grafana_health():
    """Verify Grafana is healthy and reachable on assigned port 3011."""
    resp = httpx.get("http://127.0.0.1:3011/api/health", timeout=5.0)
    assert resp.status_code == 200
    assert resp.json().get("database") == "ok"


@pytest.mark.integration
def test_alertmanager_health():
    """Verify Alertmanager is healthy on assigned port 9093."""
    resp = httpx.get("http://127.0.0.1:9093/-/healthy", timeout=5.0)
    assert resp.status_code == 200
    assert "OK" in resp.text


@pytest.mark.integration
def test_webhook_sink_health():
    """Verify Webhook Sink is healthy on port 8012."""
    resp = httpx.get("http://127.0.0.1:8012/health", timeout=5.0)
    assert resp.status_code == 200
    assert resp.json().get("status") == "ok"


@pytest.mark.integration
def test_loki_api_query_demo_app_logs():
    """Verify Loki API receives and returns logs from demo-app."""
    url = "http://127.0.0.1:3100/loki/api/v1/query_range"
    params = {"query": '{job="demo-app"}'}

    logs_found = False
    for _ in range(15):
        try:
            resp = httpx.get(url, params=params, timeout=5.0)
            if resp.status_code == 200:
                data = resp.json()
                results = data.get("data", {}).get("result", [])
                if results and len(results) > 0:
                    logs_found = True
                    break
        except Exception:
            pass
        time.sleep(2)

    assert logs_found, "Loki did not return logs for {job=\"demo-app\"}"
