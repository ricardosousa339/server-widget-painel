from __future__ import annotations

from pydantic import BaseModel, Field


class DoorbellTriggerRequest(BaseModel):
    duration_seconds: int | None = Field(default=None, ge=1, le=3600)
    source: str | None = Field(default=None, max_length=80)

    def normalized_duration_seconds(self) -> int | None:
        if self.duration_seconds is None:
            return None
        return int(self.duration_seconds)

    def normalized_source(self) -> str | None:
        if self.source is None:
            return None

        source = self.source.strip()
        if not source:
            return None
        return source[:80]
