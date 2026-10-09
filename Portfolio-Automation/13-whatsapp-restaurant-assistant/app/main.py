import asyncio
import contextlib
from collections.abc import AsyncIterator

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware

from app.admin import router as admin_router
from app.config import settings
from app.database import check_dependencies
from app.reminders import reminder_loop
from app.web_chat import router as web_chat_router
from app.webhook import router as webhook_router


@contextlib.asynccontextmanager
async def lifespan(fastapi_app: FastAPI) -> AsyncIterator[None]:
    """Starts the W9 reminder loop once per process and cancels it cleanly on shutdown."""
    task = asyncio.create_task(reminder_loop())
    try:
        yield
    finally:
        task.cancel()
        with contextlib.suppress(asyncio.CancelledError):
            await task


def create_app(*, dev_mode: bool) -> FastAPI:
    fastapi_app = FastAPI(title="Sabor de Casa — WhatsApp Restaurant Assistant", lifespan=lifespan)
    fastapi_app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.web_cors_origins_list,
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )
    fastapi_app.include_router(webhook_router)
    fastapi_app.include_router(web_chat_router)
    fastapi_app.include_router(admin_router)

    import os

    from fastapi.staticfiles import StaticFiles

    # Serve 22-web-chat-widget at /widget
    widget_dir = os.path.join(os.path.dirname(__file__), "..", "..", "22-web-chat-widget")
    fastapi_app.mount("/widget", StaticFiles(directory=widget_dir, html=True), name="widget")

    if dev_mode:
        from app.dev_chat import router as dev_chat_router

        fastapi_app.include_router(dev_chat_router)

    @fastapi_app.get("/health")
    async def health() -> dict[str, str]:
        try:
            await check_dependencies()
        except Exception as exc:
            raise HTTPException(status_code=503, detail="Dependency unavailable") from exc
        return {"status": "healthy"}

    return fastapi_app


app = create_app(dev_mode=settings.DEV_MODE)
