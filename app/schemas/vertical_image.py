from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, Field


class VerticalImageUpdateRequest(BaseModel):
    active: bool | None = None
    scroll_speed_pps: int | None = Field(default=None, ge=1, le=120)
    scroll_direction: Literal["up", "down"] | None = None

    def normalized_scroll_speed_pps(self) -> int | None:
        if self.scroll_speed_pps is None:
            return None
        return int(self.scroll_speed_pps)

    def normalized_scroll_direction(self) -> str | None:
        if self.scroll_direction is None:
            return None
        return str(self.scroll_direction)


class VerticalImageAssetUpdateRequest(BaseModel):
    active: bool | None = None
