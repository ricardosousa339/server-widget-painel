from __future__ import annotations

import base64
import io
from typing import Literal

import requests
from PIL import Image, ImageOps


ImageMode = Literal["rgb565_base64", "rgb_base64", "rgb_array"]


class ImageProcessingError(Exception):
    pass


class ImageProcessor:
    def __init__(self, size: int = 32, timeout_seconds: float = 6.0) -> None:
        self.size = size
        self.timeout_seconds = timeout_seconds

    def process_from_url(self, url: str, image_mode: ImageMode = "rgb565_base64") -> dict:
        image = self._download_image(url)
        return self.process_image(image, image_mode=image_mode)

    def process_image(self, image: Image.Image, image_mode: ImageMode = "rgb565_base64") -> dict:
        normalized = self._normalize_image(image)

        if image_mode == "rgb_array":
            rgb_bytes = normalized.tobytes()
            pixels = [
                [rgb_bytes[i], rgb_bytes[i + 1], rgb_bytes[i + 2]]
                for i in range(0, len(rgb_bytes), 3)
            ]
            return {
                "w": self.size,
                "h": self.size,
                "enc": "rgb_array",
                "data": pixels,
            }

        if image_mode == "rgb_base64":
            rgb_bytes = normalized.tobytes()
            payload = base64.b64encode(rgb_bytes).decode("ascii")
            return {
                "w": self.size,
                "h": self.size,
                "enc": "rgb_base64",
                "data": payload,
            }

        rgb565_bytes = self._to_rgb565_bytes(normalized)
        payload = base64.b64encode(rgb565_bytes).decode("ascii")
        return {
            "w": self.size,
            "h": self.size,
            "enc": "rgb565_base64",
            "data": payload,
        }

    def _download_image(self, url: str) -> Image.Image:
        try:
            response = requests.get(url, timeout=self.timeout_seconds)
            response.raise_for_status()
        except requests.RequestException as exc:
            raise ImageProcessingError(f"Falha ao baixar imagem: {exc}") from exc

        try:
            return Image.open(io.BytesIO(response.content))
        except OSError as exc:
            raise ImageProcessingError("Conteudo retornado nao e uma imagem valida") from exc

    def _normalize_image(self, image: Image.Image) -> Image.Image:
        resampling = getattr(Image, "Resampling", Image)
        rgb_image = image.convert("RGB")
        return ImageOps.fit(
            rgb_image,
            (self.size, self.size),
            method=resampling.LANCZOS,
        )

    def _to_rgb565_bytes(self, image: Image.Image) -> bytes:
        rgb_bytes = image.tobytes()
        rgb565 = bytearray()

        for i in range(0, len(rgb_bytes), 3):
            red = rgb_bytes[i]
            green = rgb_bytes[i + 1]
            blue = rgb_bytes[i + 2]

            value = ((red & 0xF8) << 8) | ((green & 0xFC) << 3) | (blue >> 3)
            rgb565.append((value >> 8) & 0xFF)
            rgb565.append(value & 0xFF)

        return bytes(rgb565)
