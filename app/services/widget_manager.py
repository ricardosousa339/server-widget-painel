from __future__ import annotations

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

    async def get_screen_payload(self, image_mode: ImageMode = "rgb565_base64") -> dict[str, Any]:
        enabled_widgets = self._enabled_widgets()
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
            "hybrid_show_seconds": display_config["hybrid_show_seconds"],
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
        hybrid_show_seconds: int | None = None,
    ) -> dict[str, Any]:
        if self.config_store is None:
            return self.get_widgets_config()

        self.config_store.update_config(
            enabled_widgets=enabled_widgets,
            display_mode=display_mode,
            hybrid_period_seconds=hybrid_period_seconds,
            hybrid_show_seconds=hybrid_show_seconds,
        )
        return self.get_widgets_config()

    def _enabled_widgets(self) -> set[str]:
        if self.config_store is None:
            return {widget.name for widget in self.all_widgets}
        return self.config_store.enabled_set()

    async def _payload_by_priority(
        self,
        enabled_widgets: set[str],
        *,
        image_mode: ImageMode,
    ) -> dict[str, Any] | None:
        for widget in self.primary_widgets:
            if widget.name not in enabled_widgets:
                continue
            payload = await widget.get_data(image_mode=image_mode)
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
            if widget.name == self.CUSTOM_WIDGET_NAME:
                continue
            if widget.name not in enabled_widgets:
                continue
            payload = await widget.get_data(image_mode=image_mode)
            if payload is not None:
                return payload

        return await self._fallback_payload(enabled_widgets, image_mode=image_mode)

    async def _payload_for_widget(
        self,
        widget_name: str,
        *,
        enabled_widgets: set[str],
        image_mode: ImageMode,
    ) -> dict[str, Any] | None:
        widget = self.primary_widget_by_name.get(widget_name)
        if widget is None:
            return None
        if widget_name not in enabled_widgets:
            return None
        return await widget.get_data(image_mode=image_mode)

    async def _fallback_payload(
        self,
        enabled_widgets: set[str],
        *,
        image_mode: ImageMode,
    ) -> dict[str, Any] | None:
        if self.fallback_widget.name not in enabled_widgets:
            return None
        return await self.fallback_widget.get_data(image_mode=image_mode)

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
                "hybrid_show_seconds": WidgetConfigStore.DEFAULT_HYBRID_SHOW_SECONDS,
            }

        state = self.config_store.get_state()
        return {
            "display_mode": str(state.get("display_mode") or WidgetConfigStore.DEFAULT_DISPLAY_MODE),
            "hybrid_period_seconds": int(
                state.get("hybrid_period_seconds")
                or WidgetConfigStore.DEFAULT_HYBRID_PERIOD_SECONDS
            ),
            "hybrid_show_seconds": int(
                state.get("hybrid_show_seconds")
                or WidgetConfigStore.DEFAULT_HYBRID_SHOW_SECONDS
            ),
        }

    @staticmethod
    def _is_hybrid_custom_window(display_config: dict[str, int | str]) -> bool:
        period = int(display_config.get("hybrid_period_seconds") or 0)
        show_seconds = int(display_config.get("hybrid_show_seconds") or 0)
        if period <= 0 or show_seconds <= 0:
            return False

        now_seconds = int(time.time())
        phase = now_seconds % period
        return phase < show_seconds
