import uuid
from datetime import datetime

from fastapi import Depends, FastAPI, HTTPException, Query

from app.database import check_dependencies
from app.models import (
    NotificationDetail,
    NotificationListResponse,
    NotifyRequest,
    NotifyResponse,
    TemplatesResponse,
)
from app.notifications import get_notification, insert_notification, list_notifications
from app.security import verify_api_key
from app.templating import (
    TemplateRenderError,
    available_templates,
    email_subject,
    render_html_template,
    render_template,
)
from app.workers.common import PRIORITY_TO_CELERY
from app.workers.discord_task import send_discord_task
from app.workers.email_task import send_email_task
from app.workers.slack_task import send_slack_task
from app.workers.telegram_task import send_telegram_task

app = FastAPI(title="Multi-Channel Notification Hub")


@app.get("/health")
async def health() -> dict[str, str]:
    try:
        await check_dependencies()
    except Exception as exc:
        raise HTTPException(status_code=503, detail="Dependency unavailable") from exc
    return {"status": "healthy"}


@app.post("/api/v1/notify", dependencies=[Depends(verify_api_key)])
async def notify(request: NotifyRequest) -> NotifyResponse:
    context = request.payload or {}
    # Render before queueing (DECISIONES-03 N5/N8): an unknown template or a missing variable
    # is a 422, and no notification row is created.
    try:
        text_body = render_template(request.template_name, context)
        html_body = (
            render_html_template(request.template_name, context)
            if "email" in request.channels
            else None
        )
        subject = (
            email_subject(request.template_name, context) if "email" in request.channels else None
        )
    except TemplateRenderError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc

    # Every requested channel gets a key in the stored `recipients` JSONB (empty list if none
    # were given, e.g. slack/discord) — this is what `app.workers.common` uses afterwards to
    # know the full set of channels a notification must reach before it is "completed".
    recipients = {channel: request.recipients.get(channel, []) for channel in request.channels}
    inserted = await insert_notification(
        request.template_name, request.priority, recipients, request.payload
    )
    notification_id = inserted["id"]
    priority = PRIORITY_TO_CELERY[request.priority]

    if "email" in request.channels:
        send_email_task.apply_async(
            args=[notification_id, recipients["email"], subject, text_body, html_body],
            priority=priority,
        )
    if "slack" in request.channels:
        send_slack_task.apply_async(args=[notification_id, text_body], priority=priority)
    if "discord" in request.channels:
        send_discord_task.apply_async(args=[notification_id, text_body], priority=priority)
    if "telegram" in request.channels:
        send_telegram_task.apply_async(
            args=[notification_id, recipients["telegram"], text_body], priority=priority
        )

    return NotifyResponse(
        notification_id=notification_id,
        status="queued",
        message="Notification queued for processing.",
    )


@app.get("/api/v1/notifications/{notification_id}", dependencies=[Depends(verify_api_key)])
async def get_notification_detail(notification_id: str) -> NotificationDetail:
    try:
        uuid.UUID(notification_id)
    except ValueError as exc:
        raise HTTPException(status_code=404, detail="Notification not found") from exc

    row = await get_notification(notification_id)
    if row is None:
        raise HTTPException(status_code=404, detail="Notification not found")
    return NotificationDetail(**row)


@app.get("/api/v1/notifications", dependencies=[Depends(verify_api_key)])
async def list_notifications_endpoint(
    status: str | None = None,
    since: str | None = None,
    limit: int = Query(50, gt=0, le=200),
) -> NotificationListResponse:
    since_dt = None
    if since is not None:
        try:
            since_dt = datetime.fromisoformat(since)
        except ValueError as exc:
            raise HTTPException(status_code=422, detail="Invalid 'since' date") from exc

    results, total = await list_notifications(status, since_dt, limit)
    return NotificationListResponse(results=results, total=total)


@app.get("/api/v1/templates", dependencies=[Depends(verify_api_key)])
async def list_templates() -> TemplatesResponse:
    return TemplatesResponse(templates=available_templates())
