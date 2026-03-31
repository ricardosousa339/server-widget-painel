from __future__ import annotations

import time
from typing import Any, Iterable

from app.services.image_service import ImageMode
from app.widgets.base import BaseWidget


class WidgetManager:
    def __init__(
        self,
        primary_widgets: Iterable[BaseWidget],
        fallback_widget: BaseWidget,
    ) -> None:
        self.primary_widgets = sorted(
            list(primary_widgets),
            key=lambda widget: widget.priority,
            reverse=True,
        )
        self.fallback_widget = fallback_widget

    async def get_screen_payload(self, image_mode: ImageMode = "rgb565_base64") -> dict[str, Any]:
        for widget in self.primary_widgets:
            payload = await widget.get_data(image_mode=image_mode)
            if payload is not None:
                return payload

        fallback_payload = await self.fallback_widget.get_data(image_mode=image_mode)
        if fallback_payload is not None:
            return fallback_payload

        return {
            "widget": "none",
            "priority": -1,
            "ts": int(time.time()),
            "data": {},
        }
