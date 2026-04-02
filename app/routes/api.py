from __future__ import annotations

from typing import Any

from fastapi import APIRouter, File, HTTPException, Query, UploadFile
from fastapi.responses import FileResponse, HTMLResponse
from fastapi import Form

from app.dependencies import (
    custom_gif_widget,
    frame_source_cache,
    frame_renderer,
    load_endpoints_guide_template,
    load_frame_preview_template,
    load_preview_template,
    load_widgets_config_template,
    widget_manager,
)
from app.schemas import (
    CustomGifAssetUpdateRequest,
    DoorbellTriggerRequest,
    WidgetConfigUpdate,
)
from app.services.image_service import ImageMode
from app.widgets.custom_gif_widget import CustomGifWidgetError

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
        "custom_gif_api": "/widgets/custom-gif",
        "custom_gif_upload": "/widgets/custom-gif/upload",
        "custom_gif_playback_api": "/widgets/custom-gif/playback",
        "doorbell_trigger_api": "/integrations/doorbell/trigger",
        "doorbell_state_api": "/integrations/doorbell/state",
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
    return widget_manager.update_config(
        enabled_widgets=update.normalized_enabled_widgets(),
        display_mode=update.normalized_display_mode(),
        hybrid_period_seconds=update.normalized_hybrid_period_seconds(),
        hybrid_show_seconds=update.normalized_hybrid_show_seconds(),
    )


@router.get("/widgets/custom-gif")
def get_custom_gif_state() -> dict[str, Any]:
    return custom_gif_widget.get_state()


@router.get("/widgets/custom-gif/raw")
def get_custom_gif_raw(
    kind: str = Query(default="custom", description="custom ou doorbell"),
    asset_id: str | None = Query(default=None, description="ID do asset especifico"),
) -> FileResponse:
    raw_path = custom_gif_widget.raw_file_path(kind=kind, asset_id=asset_id)
    if raw_path is None:
        raise HTTPException(status_code=404, detail="Nenhum GIF configurado")

    return FileResponse(path=str(raw_path), media_type="image/gif", filename=raw_path.name)


@router.post("/widgets/custom-gif/upload")
async def upload_custom_gif(
    file: UploadFile = File(...),
    kind: str = Form(default="custom"),
    active: bool = Form(default=True),
) -> dict[str, Any]:
    raw_bytes = await file.read()
    try:
        return custom_gif_widget.save_gif(
            filename=file.filename or "custom.gif",
            content_type=file.content_type or "image/gif",
            raw_bytes=raw_bytes,
            kind=kind,
            active=active,
        )
    except CustomGifWidgetError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@router.get("/widgets/custom-gif/playback")
def get_custom_gif_playback(
    kind: str = Query(default="custom", description="custom ou doorbell"),
    asset_id: str | None = Query(default=None, description="ID do asset especifico"),
    playhead_ms: int | None = Query(default=None, description="Posicao inicial da animacao em ms"),
) -> dict[str, Any]:
    payload = custom_gif_widget.playback_package(
        kind=kind,
        asset_id=asset_id,
        playhead_ms=playhead_ms,
    )
    if payload is None:
        raise HTTPException(status_code=404, detail="Nenhum GIF configurado")
    return payload


@router.patch("/widgets/custom-gif/{asset_id}")
def update_custom_gif_asset(
    asset_id: str,
    update: CustomGifAssetUpdateRequest,
) -> dict[str, Any]:
    try:
        return custom_gif_widget.update_asset(asset_id, active=update.active)
    except CustomGifWidgetError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc


@router.delete("/widgets/custom-gif/{asset_id}")
def delete_custom_gif_asset(asset_id: str) -> dict[str, Any]:
    try:
        return custom_gif_widget.delete_asset(asset_id)
    except CustomGifWidgetError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc


@router.delete("/widgets/custom-gif")
def delete_custom_gif(kind: str = Query(default="custom", description="custom ou doorbell")) -> dict[str, Any]:
    try:
        return custom_gif_widget.clear_gif(kind=kind)
    except CustomGifWidgetError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@router.get("/integrations/doorbell/state")
def get_doorbell_state() -> dict[str, Any]:
    return widget_manager.get_doorbell_alert_state()


@router.post("/integrations/doorbell/trigger")
def trigger_doorbell_alert(trigger: DoorbellTriggerRequest | None = None) -> dict[str, Any]:
    payload = trigger or DoorbellTriggerRequest()
    state = widget_manager.trigger_doorbell_alert(
        duration_seconds=payload.normalized_duration_seconds(),
        source=payload.normalized_source(),
    )
    return {"ok": True, "doorbell_alert": state}


@router.delete("/integrations/doorbell/state")
def clear_doorbell_state() -> dict[str, Any]:
    state = widget_manager.clear_doorbell_alert()
    return {"ok": True, "doorbell_alert": state}


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
