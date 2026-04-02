from __future__ import annotations

import time
from typing import Any, Iterable

from app.services.image_service import ImageMode
from app.services.widget_config_store import WidgetConfigStore
from app.widgets.base import BaseWidget


class WidgetManager:
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

    async def get_screen_payload(self, image_mode: ImageMode = "rgb565_base64") -> dict[str, Any]:
        enabled_widgets = self._enabled_widgets()

        for widget in self.primary_widgets:
            if widget.name not in enabled_widgets:
                continue
            payload = await widget.get_data(image_mode=image_mode)
            if payload is not None:
                return payload

        if self.fallback_widget.name in enabled_widgets:
            fallback_payload = await self.fallback_widget.get_data(image_mode=image_mode)
            if fallback_payload is not None:
                return fallback_payload

        return {
            "widget": "none",
            "priority": -1,
            "ts": int(time.time()),
            "data": {},
        }

    def get_widgets_config(self) -> dict[str, Any]:
        enabled_widgets = self._enabled_widgets()
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
            "updated_at": updated_at,
        }

    def update_enabled_widgets(self, enabled_widgets: Iterable[str]) -> dict[str, Any]:
        if self.config_store is None:
            return self.get_widgets_config()

        self.config_store.update_enabled_widgets(enabled_widgets)
        return self.get_widgets_config()

    def _enabled_widgets(self) -> set[str]:
        if self.config_store is None:
            return {widget.name for widget in self.all_widgets}
        return self.config_store.enabled_set()
