from __future__ import annotations

import json
from pathlib import Path
import time
from typing import Any

from app.services.image_service import ImageMode, ImageProcessor, ImageProcessingError
from app.widgets.base import BaseWidget


class BookWidget(BaseWidget):
    name = "book"

    def __init__(
        self,
        image_processor: ImageProcessor,
        state_path: Path,
        priority: int = 50,
    ) -> None:
        super().__init__(priority=priority)
        self.image_processor = image_processor
        self.state_path = state_path
        self._ensure_state_file()

    def get_state(self) -> dict[str, Any]:
        return self._load_state()

    def update_state(self, state_update: dict[str, Any]) -> dict[str, Any]:
        current = self._load_state()
        current.update(state_update)
        self._save_state(current)
        return current

    async def get_data(self, image_mode: ImageMode = "rgb565_base64") -> dict[str, Any] | None:
        state = self._load_state()
        if not state.get("is_reading"):
            return None

        payload: dict[str, Any] = {
            "widget": self.name,
            "priority": self.priority,
            "ts": int(time.time()),
            "data": {
                "reading": True,
                "title": state.get("title", ""),
                "author": state.get("author", ""),
            },
        }

        cover_url = state.get("cover_url")
        if cover_url:
            try:
                payload["data"]["cover"] = self.image_processor.process_from_url(
                    cover_url,
                    image_mode=image_mode,
                )
            except ImageProcessingError:
                payload["data"]["cover"] = None

        return payload

    def _ensure_state_file(self) -> None:
        self.state_path.parent.mkdir(parents=True, exist_ok=True)
        if not self.state_path.exists():
            self._save_state(
                {
                    "is_reading": False,
                    "title": "",
                    "author": "",
                    "cover_url": "",
                }
            )

    def _load_state(self) -> dict[str, Any]:
        try:
            content = self.state_path.read_text(encoding="utf-8")
            return json.loads(content)
        except (OSError, json.JSONDecodeError):
            return {
                "is_reading": False,
                "title": "",
                "author": "",
                "cover_url": "",
            }

    def _save_state(self, state: dict[str, Any]) -> None:
        self.state_path.write_text(
            json.dumps(state, ensure_ascii=False, separators=(",", ":")),
            encoding="utf-8",
        )
