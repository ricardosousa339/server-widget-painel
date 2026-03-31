from __future__ import annotations

from abc import ABC, abstractmethod
from typing import Any

from app.services.image_service import ImageMode


class BaseWidget(ABC):
    name: str = "base"
    priority: int = 0

    def __init__(self, priority: int | None = None) -> None:
        if priority is not None:
            self.priority = priority

    @abstractmethod
    async def get_data(self, image_mode: ImageMode = "rgb565_base64") -> dict[str, Any] | None:
        """Retorna payload do widget ou None quando nao estiver ativo."""
