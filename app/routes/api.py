from __future__ import annotations

from typing import Any

from fastapi import APIRouter, Query
from fastapi.responses import HTMLResponse

from app.dependencies import (
    book_widget,
    frame_source_cache,
    frame_renderer,
    load_endpoints_guide_template,
    load_frame_preview_template,
    load_preview_template,
    load_widgets_config_template,
    widget_manager,
)
from app.schemas import BookStateUpdate, WidgetConfigUpdate
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
        "friendly_docs": "/endpoints",
        "widgets_config_ui": "/config/widgets",
        "widgets_config_api": "/widgets/config",
        "health": "/health",
        "screen": "/screen",
        "screen_frame": "/screen/frame",
        "preview": "/preview/painel",
        "preview_frame": "/preview/frame",
    }


@router.get("/preview/painel", response_class=HTMLResponse)
def preview_painel() -> HTMLResponse:
    return HTMLResponse(content=load_preview_template())


@router.get("/endpoints", response_class=HTMLResponse)
def endpoints_guide() -> HTMLResponse:
    return HTMLResponse(content=load_endpoints_guide_template())


@router.get("/config/widgets", response_class=HTMLResponse)
def widgets_config_page() -> HTMLResponse:
    return HTMLResponse(content=load_widgets_config_template())


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


@router.get("/widgets/config")
def get_widgets_config() -> dict[str, Any]:
    return widget_manager.get_widgets_config()


@router.post("/widgets/config")
def update_widgets_config(update: WidgetConfigUpdate) -> dict[str, Any]:
    return widget_manager.update_enabled_widgets(update.normalized_enabled_widgets())


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
