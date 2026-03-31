from __future__ import annotations

from contextlib import asynccontextmanager
import logging
from typing import Any

from fastapi import FastAPI, HTTPException, Query
from pydantic import BaseModel
import uvicorn

from app.config import get_settings
from app.services.image_service import ImageMode, ImageProcessor
from app.services.skoob_service import SkoobSyncError, SkoobSyncService
from app.services.widget_manager import WidgetManager
from app.widgets.book_widget import BookWidget
from app.widgets.clock_widget import ClockWidget
from app.widgets.spotify_widget import SpotifyWidget


logger = logging.getLogger("server_widget_painel")


class BookStateUpdate(BaseModel):
    is_reading: bool | None = None
    title: str | None = None
    author: str | None = None
    cover_url: str | None = None

    def to_payload(self) -> dict[str, Any]:
        return {key: value for key, value in self.model_dump().items() if value is not None}


class SkoobSyncRequest(BaseModel):
    profile_url: str | None = None
    user_id: str | None = None
    auth_cookie: str | None = None


settings = get_settings()
image_processor = ImageProcessor(
    size=settings.image_size,
    timeout_seconds=settings.request_timeout_seconds,
)
skoob_sync_service = SkoobSyncService(
    profile_url=settings.skoob_profile_url,
    user_id=settings.skoob_user_id,
    auth_cookie=settings.skoob_auth_cookie,
    reading_types=settings.skoob_reading_types,
    timeout_seconds=settings.request_timeout_seconds,
)
spotify_widget = SpotifyWidget(settings=settings, image_processor=image_processor, priority=100)
book_widget = BookWidget(
    image_processor=image_processor,
    state_path=settings.book_state_path,
    priority=50,
    skoob_sync_service=skoob_sync_service,
    sync_interval_seconds=(
        settings.skoob_sync_interval_seconds if settings.skoob_sync_enabled else 0
    ),
)
clock_widget = ClockWidget(priority=0)
widget_manager = WidgetManager(
    primary_widgets=[spotify_widget, book_widget],
    fallback_widget=clock_widget,
)

@asynccontextmanager
async def lifespan(app: FastAPI):
    logger.info("LED Panel Backend iniciado com sucesso")
    print("[server-widget-painel] API ativa em http://0.0.0.0:8000")
    print("[server-widget-painel] Endpoints úteis: /health, /screen, /docs")
    yield


app = FastAPI(
    title="LED Panel Backend",
    version="1.0.0",
    description="Backend FastAPI para painel LED 64x32 com ESP32.",
    lifespan=lifespan,
)


@app.get("/health")
def health() -> dict[str, str]:
    return {"status": "ok"}


@app.get("/")
def root() -> dict[str, Any]:
    return {
        "status": "running",
        "service": "LED Panel Backend",
        "version": app.version,
        "docs": "/docs",
        "health": "/health",
        "screen": "/screen",
    }


@app.get("/screen")
async def screen(
    img_mode: ImageMode = Query(
        default="rgb565_base64",
        description="Formato da imagem para ESP32: rgb565_base64, rgb_base64, rgb_array",
    ),
) -> dict[str, Any]:
    return await widget_manager.get_screen_payload(image_mode=img_mode)


@app.get("/book/current")
def get_current_book() -> dict[str, Any]:
    return book_widget.get_state()


@app.post("/book/current")
def update_current_book(update: BookStateUpdate) -> dict[str, Any]:
    payload = update.to_payload()
    return book_widget.update_state(payload)


@app.post("/book/sync/skoob")
def sync_book_from_skoob(request: SkoobSyncRequest | None = None) -> dict[str, Any]:
    sync_request = request or SkoobSyncRequest()
    try:
        return book_widget.sync_from_skoob(
            force=True,
            profile_url=sync_request.profile_url,
            user_id=sync_request.user_id,
            auth_cookie=sync_request.auth_cookie,
        )
    except SkoobSyncError as exc:
        raise HTTPException(status_code=502, detail=str(exc)) from exc
    except RuntimeError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@app.get("/book/sync/skoob/status")
def get_skoob_sync_status() -> dict[str, Any]:
    status = book_widget.get_sync_status()
    return {
        "sync": status,
        "config": {
            "profile_url": settings.skoob_profile_url,
            "user_id": settings.skoob_user_id,
            "auth_cookie_configured": bool(settings.skoob_auth_cookie.strip()),
            "reading_types": list(settings.skoob_reading_types),
            "sync_enabled": settings.skoob_sync_enabled,
            "sync_interval_seconds": settings.skoob_sync_interval_seconds,
        },
    }


if __name__ == "__main__":
    uvicorn.run(
        "app.main:app",
        host="0.0.0.0",
        port=8000,
        reload=False,
        log_level="info",
        access_log=True,
    )
