import time
from collections import defaultdict

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field

from app.conversation import process_incoming_message

router = APIRouter()


class WebChatRequest(BaseModel):
    session_id: str = Field(min_length=1, max_length=100)
    text: str = Field(min_length=1, max_length=1000)


class WebChatResponse(BaseModel):
    replies: list[str]


_web_rate_limits: dict[str, list[float]] = defaultdict(list)
WEB_RATE_LIMIT_PER_MIN = 30


@router.post("/web/chat")
async def web_chat(request: WebChatRequest) -> WebChatResponse:
    now = time.time()
    _web_rate_limits[request.session_id] = [
        t for t in _web_rate_limits[request.session_id] if now - t < 60
    ]
    if len(_web_rate_limits[request.session_id]) >= WEB_RATE_LIMIT_PER_MIN:
        raise HTTPException(status_code=429, detail="Límite de mensajes por minuto excedido.")
    _web_rate_limits[request.session_id].append(now)

    # Identificamos el cliente web con el prefijo web_
    wa_id = f"web_{request.session_id}"
    replies = await process_incoming_message(wa_id, None, "text", request.text)
    return WebChatResponse(replies=replies)
