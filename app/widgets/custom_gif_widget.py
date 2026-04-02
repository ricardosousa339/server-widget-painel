from __future__ import annotations

import base64
import io
import json
from pathlib import Path
import time
from typing import Any

from PIL import Image, ImageOps, ImageSequence

from app.services.image_service import ImageMode
from app.widgets.base import BaseWidget


class CustomGifWidgetError(Exception):
    pass


class CustomGifWidget(BaseWidget):
    name = "custom_gif"

    def __init__(
        self,
        state_path: Path,
        upload_dir: Path,
        priority: int = 80,
        frame_width: int = 64,
        frame_height: int = 32,
        max_upload_bytes: int = 8 * 1024 * 1024,
    ) -> None:
        super().__init__(priority=priority)
        self.state_path = state_path
        self.upload_dir = upload_dir
        self.upload_path = self.upload_dir / "custom.gif"
        self.frame_width = frame_width
        self.frame_height = frame_height
        self.max_upload_bytes = max_upload_bytes

        self._cached_mtime: float | None = None
        self._cached_frames: list[Image.Image] = []
        self._cached_durations_ms: list[int] = []
        self._cached_total_duration_ms: int = 0

        self._ensure_paths()

    async def get_data(self, image_mode: ImageMode = "rgb565_base64") -> dict[str, Any] | None:
        if not self.upload_path.exists():
            return None

        try:
            self._ensure_cache()
        except CustomGifWidgetError:
            return None

        if not self._cached_frames:
            return None

        now_ms = int(time.time() * 1000)
        frame_index = self._frame_index_for_time(now_ms)
        frame = self._cached_frames[frame_index]

        state = self._read_state()
        return {
            "widget": self.name,
            "priority": self.priority,
            "ts": int(time.time()),
            "data": {
                "name": str(state.get("original_name") or "custom.gif"),
                "frame_index": frame_index,
                "frame_count": len(self._cached_frames),
                "total_duration_ms": self._cached_total_duration_ms,
                "frame": self._encode_frame_payload(frame, image_mode=image_mode),
            },
        }

    def get_state(self) -> dict[str, Any]:
        state = self._normalize_state(self._read_state())
        has_file = self.upload_path.exists()
        if not has_file:
            state["frame_count"] = 0
            state["total_duration_ms"] = 0
            state["size_bytes"] = 0

        state["has_file"] = has_file
        state["preview_url"] = "/widgets/custom-gif/raw" if has_file else None
        state["max_upload_bytes"] = self.max_upload_bytes
        return state

    def save_gif(self, *, filename: str, content_type: str, raw_bytes: bytes) -> dict[str, Any]:
        if not raw_bytes:
            raise CustomGifWidgetError("Arquivo vazio")

        if len(raw_bytes) > self.max_upload_bytes:
            raise CustomGifWidgetError(
                f"Arquivo muito grande (limite {self.max_upload_bytes} bytes)"
            )

        safe_name = self._sanitize_filename(filename)

        self._validate_gif(raw_bytes)

        self.upload_dir.mkdir(parents=True, exist_ok=True)
        self.upload_path.write_bytes(raw_bytes)

        self._invalidate_cache()
        self._ensure_cache()

        state = self._normalize_state(self._read_state())
        state.update(
            {
                "original_name": safe_name,
                "content_type": content_type or "image/gif",
                "uploaded_at": int(time.time()),
                "size_bytes": len(raw_bytes),
                "frame_count": len(self._cached_frames),
                "total_duration_ms": self._cached_total_duration_ms,
            }
        )
        self._write_state(state)
        return self.get_state()

    def clear_gif(self) -> dict[str, Any]:
        if self.upload_path.exists():
            self.upload_path.unlink()

        self._invalidate_cache()
        self._write_state(self._default_state())
        return self.get_state()

    def raw_file_path(self) -> Path | None:
        if not self.upload_path.exists():
            return None
        return self.upload_path

    def _ensure_paths(self) -> None:
        self.state_path.parent.mkdir(parents=True, exist_ok=True)
        self.upload_dir.mkdir(parents=True, exist_ok=True)
        if not self.state_path.exists():
            self._write_state(self._default_state())

    def _default_state(self) -> dict[str, Any]:
        return {
            "original_name": "",
            "content_type": "image/gif",
            "uploaded_at": None,
            "size_bytes": 0,
            "frame_count": 0,
            "total_duration_ms": 0,
        }

    def _read_state(self) -> dict[str, Any]:
        try:
            content = self.state_path.read_text(encoding="utf-8")
            parsed = json.loads(content)
            if isinstance(parsed, dict):
                return parsed
        except (OSError, json.JSONDecodeError):
            pass
        return self._default_state()

    def _write_state(self, state: dict[str, Any]) -> None:
        self.state_path.write_text(
            json.dumps(state, ensure_ascii=False, separators=(",", ":")),
            encoding="utf-8",
        )

    def _normalize_state(self, state: dict[str, Any]) -> dict[str, Any]:
        normalized = dict(self._default_state())
        for key in normalized:
            if key in state:
                normalized[key] = state[key]
        return normalized

    def _validate_gif(self, raw_bytes: bytes) -> None:
        try:
            with Image.open(io.BytesIO(raw_bytes)) as image:
                if str(image.format or "").upper() != "GIF":
                    raise CustomGifWidgetError("Arquivo deve ser GIF")
                image.verify()
        except CustomGifWidgetError:
            raise
        except OSError as exc:
            raise CustomGifWidgetError("Arquivo GIF invalido") from exc

    def _invalidate_cache(self) -> None:
        self._cached_mtime = None
        self._cached_frames = []
        self._cached_durations_ms = []
        self._cached_total_duration_ms = 0

    def _ensure_cache(self) -> None:
        if not self.upload_path.exists():
            self._invalidate_cache()
            return

        mtime = self.upload_path.stat().st_mtime
        if self._cached_mtime == mtime and self._cached_frames:
            return

        try:
            with Image.open(self.upload_path) as image:
                frames: list[Image.Image] = []
                durations_ms: list[int] = []
                total_ms = 0

                for frame in ImageSequence.Iterator(image):
                    duration = int(frame.info.get("duration", 100) or 100)
                    if duration <= 0:
                        duration = 100

                    normalized = self._normalize_frame(frame)
                    frames.append(normalized)
                    durations_ms.append(duration)
                    total_ms += duration
        except OSError as exc:
            raise CustomGifWidgetError("Falha ao ler GIF salvo") from exc

        if not frames:
            raise CustomGifWidgetError("GIF sem frames renderizaveis")

        self._cached_mtime = mtime
        self._cached_frames = frames
        self._cached_durations_ms = durations_ms
        self._cached_total_duration_ms = max(1, total_ms)

    def _frame_index_for_time(self, now_ms: int) -> int:
        if not self._cached_frames:
            return 0

        if len(self._cached_frames) == 1:
            return 0

        total_ms = max(1, self._cached_total_duration_ms)
        phase = now_ms % total_ms

        acc = 0
        for index, duration in enumerate(self._cached_durations_ms):
            acc += duration
            if phase < acc:
                return index

        return len(self._cached_frames) - 1

    def _normalize_frame(self, frame: Image.Image) -> Image.Image:
        rgba = frame.convert("RGBA")
        composed = Image.new("RGBA", rgba.size, (0, 0, 0, 255))
        composed.alpha_composite(rgba)

        resampling = getattr(Image, "Resampling", Image)
        fitted = ImageOps.fit(
            composed.convert("RGB"),
            (self.frame_width, self.frame_height),
            method=resampling.LANCZOS,
        )
        return fitted

    def _encode_frame_payload(self, image: Image.Image, image_mode: ImageMode) -> dict[str, Any]:
        if image_mode == "rgb_array":
            rgb_bytes = image.tobytes()
            pixels = [
                [rgb_bytes[i], rgb_bytes[i + 1], rgb_bytes[i + 2]]
                for i in range(0, len(rgb_bytes), 3)
            ]
            return {
                "w": self.frame_width,
                "h": self.frame_height,
                "enc": "rgb_array",
                "data": pixels,
            }

        if image_mode == "rgb_base64":
            rgb_bytes = image.tobytes()
            payload = base64.b64encode(rgb_bytes).decode("ascii")
            return {
                "w": self.frame_width,
                "h": self.frame_height,
                "enc": "rgb_base64",
                "data": payload,
            }

        rgb565_bytes = self._to_rgb565_bytes(image)
        payload = base64.b64encode(rgb565_bytes).decode("ascii")
        return {
            "w": self.frame_width,
            "h": self.frame_height,
            "enc": "rgb565_base64",
            "data": payload,
        }

    def _to_rgb565_bytes(self, image: Image.Image) -> bytes:
        rgb = image.convert("RGB")
        rgb_bytes = rgb.tobytes()
        rgb565 = bytearray()

        for index in range(0, len(rgb_bytes), 3):
            red = rgb_bytes[index]
            green = rgb_bytes[index + 1]
            blue = rgb_bytes[index + 2]

            value = ((red & 0xF8) << 8) | ((green & 0xFC) << 3) | (blue >> 3)
            rgb565.append((value >> 8) & 0xFF)
            rgb565.append(value & 0xFF)

        return bytes(rgb565)

    def _sanitize_filename(self, filename: str) -> str:
        safe = Path(str(filename or "custom.gif")).name
        return safe or "custom.gif"
