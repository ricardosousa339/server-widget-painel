from __future__ import annotations

from typing import Any

from fastapi import APIRouter, Query
from fastapi.responses import HTMLResponse

from app.dependencies import book_widget, load_preview_template, widget_manager
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
        "preview": "/preview/painel",
    }


@router.get("/preview/painel", response_class=HTMLResponse)
def preview_painel() -> HTMLResponse:
    return HTMLResponse(content=load_preview_template())


@router.get("/screen")
async def screen(
    img_mode: ImageMode = Query(
        default="rgb565_base64",
        description="Formato da imagem para ESP32: rgb565_base64, rgb_base64, rgb_array",
    ),
) -> dict[str, Any]:
    return await widget_manager.get_screen_payload(image_mode=img_mode)


@router.get("/book/current")
def get_current_book() -> dict[str, Any]:
    return book_widget.get_state()


@router.post("/book/current")
def update_current_book(update: BookStateUpdate) -> dict[str, Any]:
    payload = update.to_payload()
    return book_widget.update_state(payload)
