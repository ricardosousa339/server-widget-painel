from __future__ import annotations

from typing import Iterable

from pydantic import BaseModel, Field


ALLOWED_DISPLAY_MODES = {"priority", "custom_only", "hybrid"}


class WidgetConfigUpdate(BaseModel):
    enabled_widgets: list[str] | None = Field(default=None)
    display_mode: str | None = Field(default=None)
    hybrid_period_seconds: int | None = Field(default=None, ge=10, le=86400)
    default_gif_duration_seconds: int | None = Field(default=None, ge=1, le=3600)

    def normalized_enabled_widgets(self) -> list[str] | None:
        if self.enabled_widgets is None:
            return None
        return _normalize_widget_names(self.enabled_widgets)

    def normalized_display_mode(self) -> str | None:
        if self.display_mode is None:
            return None

        mode = self.display_mode.strip().lower()
        if mode not in ALLOWED_DISPLAY_MODES:
            return None
        return mode

    def normalized_hybrid_period_seconds(self) -> int | None:
        if self.hybrid_period_seconds is None:
            return None
        return int(self.hybrid_period_seconds)

    def normalized_default_gif_duration_seconds(self) -> int | None:
        if self.default_gif_duration_seconds is None:
            return None
        return int(self.default_gif_duration_seconds)


def _normalize_widget_names(values: Iterable[str]) -> list[str]:
    normalized: list[str] = []
    for value in values:
        name = value.strip().lower()
        if not name:
            continue
        if name not in normalized:
            normalized.append(name)
    return normalized