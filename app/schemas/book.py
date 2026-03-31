from __future__ import annotations

from typing import Any

from pydantic import BaseModel


class BookStateUpdate(BaseModel):
    is_reading: bool | None = None
    title: str | None = None
    author: str | None = None
    cover_url: str | None = None

    def to_payload(self) -> dict[str, Any]:
        return {key: value for key, value in self.model_dump().items() if value is not None}
