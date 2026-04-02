from __future__ import annotations

from pydantic import BaseModel


class CustomGifAssetUpdateRequest(BaseModel):
    active: bool | None = None