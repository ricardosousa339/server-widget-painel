from __future__ import annotations

from pydantic import BaseModel, Field


class VerticalImageUpdateRequest(BaseModel):
    active: bool | None = None
    scroll_speed_pps: int | None = Field(default=None, ge=1, le=120)

    def normalized_scroll_speed_pps(self) -> int | None:
        if self.scroll_speed_pps is None:
            return None
        return int(self.scroll_speed_pps)
