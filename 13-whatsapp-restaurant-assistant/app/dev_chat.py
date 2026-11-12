"""Dev-mode chat endpoint (DECISIONES-13 W5): runs the exact same conversation pipeline as the
real webhook but returns the replies as JSON instead of sending them to WhatsApp. Only registered
in `app.main` when `settings.DEV_MODE` is true; bearer-protected with `DEV_API_KEY`.
"""

from fastapi import APIRouter, Depends
from pydantic import BaseModel, Field

from app.conversation import process_incoming_message
from app.security import verify_dev_api_key

router = APIRouter()


class DevChatRequest(BaseModel):
    wa_id: str = Field(min_length=1, max_length=20)
    text: str = Field(min_length=1, max_length=4096)


class DevChatResponse(BaseModel):
    replies: list[str]


@router.post("/dev/chat", dependencies=[Depends(verify_dev_api_key)])
async def dev_chat(request: DevChatRequest) -> DevChatResponse:
    # No `message_id`: dev-mode messages are never deduped, same as a brand new Meta message id
    # each time.
    replies = await process_incoming_message(request.wa_id, None, "text", request.text)
    return DevChatResponse(replies=replies)
