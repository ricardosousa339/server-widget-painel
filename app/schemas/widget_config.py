from __future__ import annotations

from typing import Iterable

from pydantic import BaseModel, Field


class WidgetConfigUpdate(BaseModel):
    enabled_widgets: list[str] = Field(default_factory=list)

    def normalized_enabled_widgets(self) -> list[str]:
        return _normalize_widget_names(self.enabled_widgets)


def _normalize_widget_names(values: Iterable[str]) -> list[str]:
    normalized: list[str] = []
    for value in values:
        name = value.strip().lower()
        if not name:
            continue
        if name not in normalized:
            normalized.append(name)
    return normalized