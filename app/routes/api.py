from __future__ import annotations

from typing import Any

from fastapi import APIRouter, Query
from fastapi.responses import HTMLResponse

from app.dependencies import (
    book_widget,
    frame_source_cache,
    frame_renderer,
    load_frame_preview_template,
    load_preview_template,
    widget_manager,
)
from app.schemas import BookStateUpdate
from app.services.image_service import ImageMode

router = APIRouter()


@router.get("/health")
def health() -> dict[str, str]:
    return {"status": "ok"}


@router.get("/")
def root() -> dict[str, Any]:
    return {
        "status": "running",
        "service": "LED Panel Backend",
        "version": "1.0.0",
        "docs": "/docs",
        "health": "/health",
        "screen": "/screen",
        "screen_frame": "/screen/frame",
        "preview": "/preview/painel",
        "preview_frame": "/preview/frame",
    }


@router.get("/preview/painel", response_class=HTMLResponse)
def preview_painel() -> HTMLResponse:
    return HTMLResponse(content=load_preview_template())


@router.get("/preview/frame", response_class=HTMLResponse)
def preview_frame() -> HTMLResponse:
    return HTMLResponse(content=load_frame_preview_template())


@router.get("/screen")
async def screen(
    img_mode: ImageMode = Query(
        default="rgb565_base64",
        description="Formato da imagem para ESP32: rgb565_base64, rgb_base64, rgb_array",
    ),
) -> dict[str, Any]:
    return await widget_manager.get_screen_payload(image_mode=img_mode)


@router.get("/screen/frame")
async def screen_frame(
    at_ms: int | None = Query(
        default=None,
        description="Timestamp em ms para gerar frame em ponto especifico da animacao",
    ),
    refresh_source: bool = Query(
        default=False,
        description="Forca refresh da fonte de dados antes de renderizar frame",
    ),
) -> dict[str, Any]:
    payload = await frame_source_cache.get_payload(force_refresh=refresh_source)
    response = frame_renderer.render_payload(payload, now_ms=at_ms)
    response["source_age_ms"] = frame_source_cache.age_ms()
    response["source_refresh_ms"] = frame_source_cache.refresh_interval_ms
    return response


@router.get("/book/current")
def get_current_book() -> dict[str, Any]:
    return book_widget.get_state()


@router.post("/book/current")
def update_current_book(update: BookStateUpdate) -> dict[str, Any]:
    payload = update.to_payload()
    return book_widget.update_state(payload)
