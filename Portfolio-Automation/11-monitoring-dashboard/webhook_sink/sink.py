import logging
import sys
from typing import Any

from fastapi import FastAPI, Request
from pydantic import BaseModel

logger = logging.getLogger("webhook_sink")
logger.setLevel(logging.INFO)

handler = logging.StreamHandler(sys.stdout)
handler.setFormatter(
    logging.Formatter("%(asctime)s [%(levelname)s] [service=webhook-sink] %(message)s")
)
logger.addHandler(handler)

app = FastAPI(
    title="Webhook Sink for Alertmanager",
    description="Local sink for testing and receiving alerts dispatched by Alertmanager",
    version="1.0.0",
)

# In-memory storage for received alerts
received_alerts: list[dict[str, Any]] = []


class ClearResponse(BaseModel):
    cleared: bool
    total_previous: int


@app.get("/health")
async def health_check() -> dict[str, str]:
    return {"status": "ok", "service": "webhook-sink", "version": "1.0.0"}


@app.post("/webhook")
@app.post("/")
async def receive_webhook(request: Request) -> dict[str, Any]:
    try:
        payload = await request.json()
    except Exception:
        payload = {"raw": (await request.body()).decode("utf-8", errors="replace")}

    received_alerts.append(payload)
    alert_names = []
    if isinstance(payload, dict) and "alerts" in payload:
        for alert in payload.get("alerts", []):
            if isinstance(alert, dict) and "labels" in alert:
                alert_names.append(alert["labels"].get("alertname", "unknown"))

    logger.info(
        "Received alert notification: status=%s count=%d alerts=%s",
        payload.get("status", "unknown") if isinstance(payload, dict) else "raw",
        len(alert_names),
        alert_names,
    )
    return {
        "status": "received",
        "alerts_recorded": len(received_alerts),
        "latest_alerts": alert_names,
    }


@app.get("/alerts")
async def list_alerts() -> dict[str, Any]:
    return {
        "count": len(received_alerts),
        "alerts": received_alerts,
    }


@app.post("/alerts/clear")
async def clear_alerts() -> ClearResponse:
    prev_count = len(received_alerts)
    received_alerts.clear()
    logger.info("Cleared %d stored alerts", prev_count)
    return ClearResponse(cleared=True, total_previous=prev_count)
