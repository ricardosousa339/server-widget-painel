from __future__ import annotations

from datetime import datetime
import time
from typing import Any

from app.services.image_service import ImageMode
from app.widgets.base import BaseWidget


class ClockWidget(BaseWidget):
    name = "clock"

    async def get_data(self, image_mode: ImageMode = "rgb565_base64") -> dict[str, Any]:
        now = datetime.now()
        return {
            "widget": self.name,
            "priority": self.priority,
            "ts": int(time.time()),
            "data": {
                "time": now.strftime("%H:%M"),
                "seconds": now.strftime("%S"),
                "date": now.strftime("%d/%m"),
                "weekday": now.strftime("%a"),
            },
        }
