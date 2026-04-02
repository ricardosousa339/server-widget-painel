from __future__ import annotations

from functools import lru_cache
from pathlib import Path

from app.config import get_settings
from app.services.frame_renderer import FrameRenderer
from app.services.image_service import ImageProcessor
from app.services.screen_payload_cache import ScreenPayloadCache
from app.services.widget_config_store import WidgetConfigStore
from app.services.widget_manager import WidgetManager
from app.widgets.clock_widget import ClockWidget
from app.widgets.custom_gif_widget import CustomGifWidget
from app.widgets.spotify_widget import SpotifyWidget

PROJECT_ROOT = Path(__file__).resolve().parent.parent
ASSETS_DIR = PROJECT_ROOT / "assets"
TEMPLATES_DIR = PROJECT_ROOT / "app" / "templates"
PREVIEW_TEMPLATE_PATH = TEMPLATES_DIR / "preview.html"
FRAME_PREVIEW_TEMPLATE_PATH = TEMPLATES_DIR / "preview_frame.html"
ENDPOINTS_GUIDE_TEMPLATE_PATH = TEMPLATES_DIR / "endpoints_guide.html"
WIDGETS_CONFIG_TEMPLATE_PATH = TEMPLATES_DIR / "widgets_config.html"

settings = get_settings()
image_processor = ImageProcessor(
    size=settings.image_size,
    timeout_seconds=settings.request_timeout_seconds,
)
spotify_widget = SpotifyWidget(settings=settings, image_processor=image_processor, priority=100)
custom_gif_widget = CustomGifWidget(
    state_path=settings.custom_gif_state_path,
    upload_dir=settings.custom_gif_upload_dir,
    priority=80,
    frame_width=64,
    frame_height=32,
    max_upload_bytes=settings.custom_gif_max_upload_bytes,
)
clock_widget = ClockWidget(priority=0)
widget_config_store = WidgetConfigStore(
    state_path=settings.widget_config_path,
    available_widgets=[spotify_widget.name, custom_gif_widget.name, clock_widget.name],
)
widget_manager = WidgetManager(
    primary_widgets=[spotify_widget, custom_gif_widget],
    fallback_widget=clock_widget,
    config_store=widget_config_store,
    doorbell_alert_default_seconds=settings.doorbell_alert_default_seconds,
    doorbell_alert_max_seconds=settings.doorbell_alert_max_seconds,
)
frame_renderer = FrameRenderer(
    width=64,
    height=32,
    font_path=ASSETS_DIR / "minecraftia.ttf",
    border_mode="strong",
)
frame_source_cache = ScreenPayloadCache(
    fetch_payload=lambda: widget_manager.get_screen_payload(image_mode="rgb565_base64"),
    refresh_interval_ms=settings.frame_source_refresh_ms,
)


@lru_cache(maxsize=1)
def load_preview_template() -> str:
    return PREVIEW_TEMPLATE_PATH.read_text(encoding="utf-8")


@lru_cache(maxsize=1)
def load_frame_preview_template() -> str:
    return FRAME_PREVIEW_TEMPLATE_PATH.read_text(encoding="utf-8")


@lru_cache(maxsize=1)
def load_endpoints_guide_template() -> str:
    return ENDPOINTS_GUIDE_TEMPLATE_PATH.read_text(encoding="utf-8")


@lru_cache(maxsize=1)
def load_widgets_config_template() -> str:
    return WIDGETS_CONFIG_TEMPLATE_PATH.read_text(encoding="utf-8")
