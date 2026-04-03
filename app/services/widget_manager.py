from __future__ import annotations

from copy import deepcopy
import time
from typing import Any, Iterable

from app.services.image_service import ImageMode
from app.services.widget_config_store import WidgetConfigStore
from app.widgets.base import BaseWidget


class WidgetManager:
    CUSTOM_WIDGET_NAME = "custom_gif"

    def __init__(
        self,
        primary_widgets: Iterable[BaseWidget],
        fallback_widget: BaseWidget,
        config_store: WidgetConfigStore | None = None,
        doorbell_alert_default_seconds: int = 8,
        doorbell_alert_max_seconds: int = 60,
        spotify_grace_seconds: int = 8,
    ) -> None:
        self.primary_widgets = sorted(
            list(primary_widgets),
            key=lambda widget: widget.priority,
            reverse=True,
        )
        self.fallback_widget = fallback_widget
        self.config_store = config_store
        self.all_widgets = [*self.primary_widgets, self.fallback_widget]
        self.primary_widget_by_name = {
            widget.name: widget for widget in self.primary_widgets
        }
        self.doorbell_alert_default_seconds = max(1, int(doorbell_alert_default_seconds))
        self.doorbell_alert_max_seconds = max(
            self.doorbell_alert_default_seconds,
            int(doorbell_alert_max_seconds),
        )
        self._doorbell_alert_until: float = 0.0
        self._doorbell_last_trigger_at: float = 0.0
        self._doorbell_last_trigger_ms: int = 0
        self._doorbell_last_source: str | None = None
        self.spotify_grace_seconds = max(0, int(spotify_grace_seconds))
        self._spotify_last_payload: dict[str, Any] | None = None
        self._spotify_last_seen_at: float = 0.0

    async def get_screen_payload(self, image_mode: ImageMode = "rgb565_base64") -> dict[str, Any]:
        enabled_widgets = self._enabled_widgets()

        spotify_payload = await self._spotify_payload_with_grace(
            enabled_widgets=enabled_widgets,
            image_mode=image_mode,
        )
        if spotify_payload is not None:
            return spotify_payload

        doorbell_state = self.get_doorbell_alert_state()
        if doorbell_state["active"]:
            playhead_ms = None
            if doorbell_state["last_trigger_ms"] is not None:
                playhead_ms = max(0, int(time.time() * 1000) - int(doorbell_state["last_trigger_ms"]))

            custom_payload = await self._payload_for_widget(
                self.CUSTOM_WIDGET_NAME,
                enabled_widgets=enabled_widgets,
                image_mode=image_mode,
                ignore_enabled=True,
                kind="doorbell",
                playhead_ms=playhead_ms,
            )
            if custom_payload is not None:
                data = custom_payload.get("data")
                if isinstance(data, dict):
                    data["doorbell_alert"] = {
                        "active": True,
                        "remaining_seconds": doorbell_state["remaining_seconds"],
                        "last_source": doorbell_state["last_source"],
                        "playhead_ms": playhead_ms,
                    }
                return custom_payload

        display_config = self._display_config()
        display_mode = display_config["display_mode"]

        if display_mode == "custom_only":
            custom_payload = await self._payload_for_widget(
                self.CUSTOM_WIDGET_NAME,
                enabled_widgets=enabled_widgets,
                image_mode=image_mode,
            )
            if custom_payload is not None:
                return custom_payload

            payload = await self._payload_without_custom(enabled_widgets, image_mode=image_mode)
            if payload is not None:
                return payload
            return self._none_payload()

        if display_mode == "hybrid":
            if self._is_hybrid_custom_window(display_config):
                custom_widgets = []
                if "vertical_image" in enabled_widgets:
                    custom_widgets.append("vertical_image")
                if self.CUSTOM_WIDGET_NAME in enabled_widgets:
                    custom_widgets.append(self.CUSTOM_WIDGET_NAME)
                
                if custom_widgets:
                    show_seconds = int(display_config.get("default_gif_duration_seconds") or 0)
                    if show_seconds > 0:
                        total_custom = len(custom_widgets)
                        now_seconds = int(time.time())
                        period = int(display_config.get("hybrid_period_seconds") or 0)
                        
                        if period > 0:
                            cycle_idx = (now_seconds // period) % total_custom
                            target_widget = custom_widgets[cycle_idx]
                            
                            custom_payload = await self._payload_for_widget(
                                target_widget,
                                enabled_widgets=enabled_widgets,
                                image_mode=image_mode,
                            )
                            if custom_payload is not None:
                                return custom_payload

            payload = await self._payload_without_custom(enabled_widgets, image_mode=image_mode)
            if payload is not None:
                return payload
            return self._none_payload()

        payload = await self._payload_by_priority(enabled_widgets, image_mode=image_mode)
        if payload is not None:
            return payload
        return self._none_payload()

    def get_widgets_config(self) -> dict[str, Any]:
        enabled_widgets = self._enabled_widgets()
        display_config = self._display_config()
        widgets = [
            {
                "name": widget.name,
                "priority": widget.priority,
                "enabled": widget.name in enabled_widgets,
                "role": "fallback" if widget.name == self.fallback_widget.name else "primary",
            }
            for widget in self.all_widgets
        ]

        updated_at: int | None = None
        if self.config_store is not None:
            updated_at_raw = self.config_store.get_state().get("updated_at")
            if isinstance(updated_at_raw, int):
                updated_at = updated_at_raw

        return {
            "widgets": widgets,
            "enabled_widgets": sorted(enabled_widgets),
            "display_mode": display_config["display_mode"],
            "hybrid_period_seconds": display_config["hybrid_period_seconds"],
            "default_gif_duration_seconds": display_config["default_gif_duration_seconds"],
            "updated_at": updated_at,
        }

    def update_enabled_widgets(self, enabled_widgets: Iterable[str]) -> dict[str, Any]:
        if self.config_store is None:
            return self.get_widgets_config()

        self.config_store.update_enabled_widgets(enabled_widgets)
        return self.get_widgets_config()

    def update_config(
        self,
        *,
        enabled_widgets: Iterable[str] | None = None,
        display_mode: str | None = None,
        hybrid_period_seconds: int | None = None,
        default_gif_duration_seconds: int | None = None,
    ) -> dict[str, Any]:
        if self.config_store is None:
            return self.get_widgets_config()

        self.config_store.update_config(
            enabled_widgets=enabled_widgets,
            display_mode=display_mode,
            hybrid_period_seconds=hybrid_period_seconds,
            default_gif_duration_seconds=default_gif_duration_seconds,
        )
        return self.get_widgets_config()

    def _enabled_widgets(self) -> set[str]:
        if self.config_store is None:
            return {widget.name for widget in self.all_widgets}
        return self.config_store.enabled_set()

    def trigger_doorbell_alert(
        self,
        *,
        duration_seconds: int | None = None,
        source: str | None = None,
    ) -> dict[str, Any]:
        now = time.time()
        duration = self._normalize_doorbell_duration(duration_seconds)
        self._doorbell_alert_until = max(self._doorbell_alert_until, now + duration)
        self._doorbell_last_trigger_at = now
        self._doorbell_last_trigger_ms = int(now * 1000)
        self._doorbell_last_source = source
        return self.get_doorbell_alert_state()

    def clear_doorbell_alert(self) -> dict[str, Any]:
        self._doorbell_alert_until = 0.0
        return self.get_doorbell_alert_state()

    def get_doorbell_alert_state(self) -> dict[str, Any]:
        now = time.time()
        remaining_seconds = max(0, int((self._doorbell_alert_until - now) + 0.999))
        active = remaining_seconds > 0
        if not active:
            self._doorbell_alert_until = 0.0

        last_trigger_ts: int | None = None
        if self._doorbell_last_trigger_at > 0:
            last_trigger_ts = int(self._doorbell_last_trigger_at)

        return {
            "active": active,
            "remaining_seconds": remaining_seconds,
            "default_seconds": self.doorbell_alert_default_seconds,
            "max_seconds": self.doorbell_alert_max_seconds,
            "last_trigger_ts": last_trigger_ts,
            "last_trigger_ms": self._doorbell_last_trigger_ms or None,
            "last_source": self._doorbell_last_source,
        }

    def _normalize_doorbell_duration(self, duration_seconds: int | None) -> int:
        if duration_seconds is None:
            return self.doorbell_alert_default_seconds

        try:
            duration = int(duration_seconds)
        except (TypeError, ValueError):
            duration = self.doorbell_alert_default_seconds

        if duration < 1:
            return 1
        if duration > self.doorbell_alert_max_seconds:
            return self.doorbell_alert_max_seconds
        return duration

    async def _payload_by_priority(
        self,
        enabled_widgets: set[str],
        *,
        image_mode: ImageMode,
    ) -> dict[str, Any] | None:
        for widget in self.primary_widgets:
            if widget.name not in enabled_widgets:
                continue
            payload = await self._safe_widget_payload(widget, image_mode=image_mode)
            if payload is not None:
                return payload

        return await self._fallback_payload(enabled_widgets, image_mode=image_mode)

    async def _payload_without_custom(
        self,
        enabled_widgets: set[str],
        *,
        image_mode: ImageMode,
    ) -> dict[str, Any] | None:
        for widget in self.primary_widgets:
            if widget.name in [self.CUSTOM_WIDGET_NAME, "vertical_image"]:
                continue
            if widget.name not in enabled_widgets:
                continue
            payload = await self._safe_widget_payload(widget, image_mode=image_mode)
            if payload is not None:
                return payload

        return await self._fallback_payload(enabled_widgets, image_mode=image_mode)

    async def _payload_for_widget(
        self,
        widget_name: str,
        *,
        enabled_widgets: set[str],
        image_mode: ImageMode,
        ignore_enabled: bool = False,
        **kwargs: Any,
    ) -> dict[str, Any] | None:
        widget = self.primary_widget_by_name.get(widget_name)
        if widget is None:
            return None
        if not ignore_enabled and widget_name not in enabled_widgets:
            return None
        return await self._safe_widget_payload(widget, image_mode=image_mode, **kwargs)

    async def _spotify_payload_with_grace(
        self,
        *,
        enabled_widgets: set[str],
        image_mode: ImageMode,
    ) -> dict[str, Any] | None:
        live_payload = await self._payload_for_widget(
            "spotify",
            enabled_widgets=enabled_widgets,
            image_mode=image_mode,
        )
        if live_payload is not None:
            self._remember_spotify_payload(live_payload)
            return live_payload

        if "spotify" not in enabled_widgets:
            self._clear_spotify_cache()
            return None

        return self._cached_spotify_payload()

    def _remember_spotify_payload(self, payload: dict[str, Any]) -> None:
        self._spotify_last_payload = deepcopy(payload)
        self._spotify_last_seen_at = time.time()

    def _cached_spotify_payload(self) -> dict[str, Any] | None:
        if self._spotify_last_payload is None or self._spotify_last_seen_at <= 0:
            return None

        if self.spotify_grace_seconds <= 0:
            self._clear_spotify_cache()
            return None

        age_seconds = time.time() - self._spotify_last_seen_at
        if age_seconds > float(self.spotify_grace_seconds):
            self._clear_spotify_cache()
            return None

        payload = deepcopy(self._spotify_last_payload)
        payload["ts"] = int(time.time())

        data = payload.get("data")
        if isinstance(data, dict):
            data["currently_playing"] = True
            data["grace_cached"] = True

        return payload

    def _clear_spotify_cache(self) -> None:
        self._spotify_last_payload = None
        self._spotify_last_seen_at = 0.0

    async def _fallback_payload(
        self,
        enabled_widgets: set[str],
        *,
        image_mode: ImageMode,
    ) -> dict[str, Any] | None:
        if self.fallback_widget.name not in enabled_widgets:
            return None
        return await self._safe_widget_payload(self.fallback_widget, image_mode=image_mode)

    @staticmethod
    async def _safe_widget_payload(
        widget: BaseWidget,
        *,
        image_mode: ImageMode,
        **kwargs: Any,
    ) -> dict[str, Any] | None:
        try:
            return await widget.get_data(image_mode=image_mode, **kwargs)
        except Exception:
            return None

    @staticmethod
    def _none_payload() -> dict[str, Any]:
        return {
            "widget": "none",
            "priority": -1,
            "ts": int(time.time()),
            "data": {},
        }

    def _display_config(self) -> dict[str, int | str]:
        if self.config_store is None:
            return {
                "display_mode": WidgetConfigStore.DEFAULT_DISPLAY_MODE,
                "hybrid_period_seconds": WidgetConfigStore.DEFAULT_HYBRID_PERIOD_SECONDS,
                "default_gif_duration_seconds": WidgetConfigStore.DEFAULT_HYBRID_SHOW_SECONDS,
            }

        state = self.config_store.get_state()
        return {
            "display_mode": str(state.get("display_mode") or WidgetConfigStore.DEFAULT_DISPLAY_MODE),
            "hybrid_period_seconds": int(
                state.get("hybrid_period_seconds")
                or WidgetConfigStore.DEFAULT_HYBRID_PERIOD_SECONDS
            ),
            "default_gif_duration_seconds": int(
                state.get("default_gif_duration_seconds")
                or WidgetConfigStore.DEFAULT_HYBRID_SHOW_SECONDS
            ),
        }

    @staticmethod
    def _is_hybrid_custom_window(display_config: dict[str, int | str]) -> bool:
        period = int(display_config.get("hybrid_period_seconds") or 0)
        show_seconds = int(display_config.get("default_gif_duration_seconds") or 0)
        if period <= 0 or show_seconds <= 0:
            return False

        now_seconds = int(time.time())
        phase = now_seconds % period
        return phase < show_seconds
