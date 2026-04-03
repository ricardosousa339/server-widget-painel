from __future__ import annotations

import base64
import io
import json
import time
import uuid
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from PIL import Image

from app.services.image_service import ImageMode
from app.widgets.base import BaseWidget


class VerticalImageWidgetError(Exception):
    pass


@dataclass(slots=True)
class VerticalImageCache:
    mtime: float
    image: Image.Image


class VerticalImageWidget(BaseWidget):
    name = "vertical_image"
    SCHEMA_VERSION = 1
    MIN_SCROLL_SPEED_PPS = 1
    MAX_SCROLL_SPEED_PPS = 120

    def __init__(
        self,
        *,
        state_path: Path,
        upload_dir: Path,
        priority: int = 70,
        frame_width: int = 64,
        frame_height: int = 32,
        max_upload_bytes: int = 8 * 1024 * 1024,
        default_scroll_speed_pps: int = 14,
    ) -> None:
        super().__init__(priority=priority)
        self.state_path = state_path
        self.upload_dir = upload_dir
        self.frame_width = frame_width
        self.frame_height = frame_height
        self.max_upload_bytes = max_upload_bytes
        self.default_scroll_speed_pps = self._normalize_scroll_speed(default_scroll_speed_pps)

        self._cache_by_asset_id: dict[str, VerticalImageCache] = {}

        self._ensure_paths()

    async def get_data(self, image_mode: ImageMode = "rgb565_base64") -> dict[str, Any] | None:
        try:
            state = self._load_state()
            asset = state.get("asset")
            if not isinstance(asset, dict):
                return None
            if not bool(asset.get("active", True)):
                return None

            source = self._ensure_source_for_asset(asset)
            now_ms = int(time.time() * 1000)
            speed_pps = self._normalize_scroll_speed(state.get("scroll_speed_pps"))
            frame, scroll_range_px, scroll_progress_px, window_start_y = self._build_viewport_frame(
                source,
                now_ms=now_ms,
                scroll_speed_pps=speed_pps,
            )
        except VerticalImageWidgetError:
            return None

        return {
            "widget": self.name,
            "priority": self.priority,
            "ts": int(time.time()),
            "data": {
                "asset_id": asset["id"],
                "asset_name": asset["name"],
                "asset_revision": asset["revision"],
                "asset_active": bool(asset["active"]),
                "source_width": int(source.width),
                "source_height": int(source.height),
                "scroll_speed_pps": speed_pps,
                "scroll_range_px": scroll_range_px,
                "scroll_progress_px": scroll_progress_px,
                "window_start_y": window_start_y,
                "raw_url": self._raw_url(asset_id=asset["id"]),
                "preview_url": self._raw_url(asset_id=asset["id"]),
                "frame": self._encode_frame_payload(frame, image_mode=image_mode),
            },
        }

    def get_state(self) -> dict[str, Any]:
        state = self._load_state()
        asset = state.get("asset")
        public_asset = self._asset_public_payload(asset)

        return {
            "schema_version": self.SCHEMA_VERSION,
            "max_upload_bytes": self.max_upload_bytes,
            "frame_width": self.frame_width,
            "frame_height": self.frame_height,
            "scroll_speed_pps": self._normalize_scroll_speed(state.get("scroll_speed_pps")),
            "asset": public_asset,
            "configured": bool(public_asset and public_asset["active"] and public_asset["available"]),
            "raw_url": self._raw_url(asset_id=public_asset["id"] if public_asset else None),
        }

    def save_image(
        self,
        *,
        filename: str,
        content_type: str,
        raw_bytes: bytes,
        active: bool = True,
    ) -> dict[str, Any]:
        if not raw_bytes:
            raise VerticalImageWidgetError("Arquivo vazio")

        if len(raw_bytes) > self.max_upload_bytes:
            raise VerticalImageWidgetError(
                f"Arquivo muito grande (limite {self.max_upload_bytes} bytes)"
            )

        normalized = self._normalize_source_image(raw_bytes)

        asset_id = uuid.uuid4().hex
        storage_relpath = self._storage_relpath(asset_id)
        file_path = self.upload_dir / storage_relpath
        file_path.parent.mkdir(parents=True, exist_ok=True)
        normalized.save(file_path, format="PNG")

        state = self._load_state()
        previous = state.get("asset")
        self._clear_asset_files(previous)
        if isinstance(previous, dict):
            self._invalidate_cache(str(previous.get("id") or ""))

        now = int(time.time())
        asset = {
            "id": asset_id,
            "name": self._sanitize_filename(filename),
            "original_name": self._sanitize_filename(filename),
            "content_type": content_type or "image/png",
            "storage_relpath": storage_relpath,
            "active": bool(active),
            "uploaded_at": now,
            "updated_at": now,
            "size_bytes": int(file_path.stat().st_size),
            "width": int(normalized.width),
            "height": int(normalized.height),
            "revision": 1,
        }
        state["asset"] = asset

        self._cache_by_asset_id[asset_id] = VerticalImageCache(
            mtime=file_path.stat().st_mtime,
            image=normalized,
        )

        self._write_state(state)
        return self.get_state()

    def update_config(
        self,
        *,
        active: bool | None = None,
        scroll_speed_pps: int | None = None,
    ) -> dict[str, Any]:
        state = self._load_state()
        changed = False

        if scroll_speed_pps is not None:
            state["scroll_speed_pps"] = self._normalize_scroll_speed(scroll_speed_pps)
            changed = True

        asset = state.get("asset")
        if isinstance(asset, dict) and active is not None:
            asset["active"] = bool(active)
            asset["updated_at"] = int(time.time())
            asset["revision"] = max(1, int(asset.get("revision") or 1)) + 1
            changed = True

        if changed:
            self._write_state(state)

        return self.get_state()

    def clear_image(self) -> dict[str, Any]:
        state = self._load_state()
        asset = state.get("asset")
        self._clear_asset_files(asset)
        if isinstance(asset, dict):
            self._invalidate_cache(str(asset.get("id") or ""))
        state["asset"] = None
        self._write_state(state)
        return self.get_state()

    def raw_file_path(self, *, asset_id: str | None = None) -> Path | None:
        state = self._load_state()
        asset = state.get("asset")
        if not isinstance(asset, dict):
            return None

        if asset_id is not None and str(asset.get("id") or "") != str(asset_id):
            return None

        file_path = self._asset_file_path(asset)
        if not file_path.exists():
            return None
        return file_path

    def _ensure_paths(self) -> None:
        self.state_path.parent.mkdir(parents=True, exist_ok=True)
        self.upload_dir.mkdir(parents=True, exist_ok=True)

    def _default_state(self) -> dict[str, Any]:
        return {
            "schema_version": self.SCHEMA_VERSION,
            "scroll_speed_pps": self.default_scroll_speed_pps,
            "asset": None,
        }

    def _load_state(self) -> dict[str, Any]:
        state = self._normalize_state(self._read_state())
        if not self.state_path.exists():
            self._write_state(state)
        return state

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
        if not isinstance(state, dict):
            return self._default_state()

        normalized = self._default_state()
        normalized["scroll_speed_pps"] = self._normalize_scroll_speed(
            state.get("scroll_speed_pps")
        )

        asset = state.get("asset")
        if isinstance(asset, dict):
            normalized["asset"] = self._normalize_asset(asset)

        return normalized

    def _normalize_asset(self, asset: dict[str, Any]) -> dict[str, Any]:
        asset_id = str(asset.get("id") or uuid.uuid4().hex)
        storage_relpath = str(asset.get("storage_relpath") or self._storage_relpath(asset_id))
        safe_name = self._sanitize_filename(
            str(asset.get("name") or asset.get("original_name") or f"{asset_id}.png")
        )

        return {
            "id": asset_id,
            "name": safe_name,
            "original_name": self._sanitize_filename(str(asset.get("original_name") or safe_name)),
            "content_type": str(asset.get("content_type") or "image/png"),
            "storage_relpath": storage_relpath,
            "active": bool(asset.get("active", True)),
            "uploaded_at": int(asset.get("uploaded_at") or 0),
            "updated_at": int(asset.get("updated_at") or asset.get("uploaded_at") or 0),
            "size_bytes": int(asset.get("size_bytes") or 0),
            "width": int(asset.get("width") or self.frame_width),
            "height": int(asset.get("height") or self.frame_height),
            "revision": max(1, int(asset.get("revision") or 1)),
        }

    def _normalize_source_image(self, raw_bytes: bytes) -> Image.Image:
        try:
            with Image.open(io.BytesIO(raw_bytes)) as image:
                rgba = image.convert("RGBA")
        except OSError as exc:
            raise VerticalImageWidgetError("Arquivo de imagem invalido") from exc

        composed = Image.new("RGBA", rgba.size, (0, 0, 0, 255))
        composed.alpha_composite(rgba)
        rgb = composed.convert("RGB")

        source_w, source_h = rgb.size
        if source_w <= 0 or source_h <= 0:
            raise VerticalImageWidgetError("Imagem com dimensoes invalidas")

        target_h = max(1, int(round(source_h * (self.frame_width / float(source_w)))))
        resampling = getattr(Image, "Resampling", Image)
        return rgb.resize((self.frame_width, target_h), resampling.LANCZOS)

    def _ensure_source_for_asset(self, asset: dict[str, Any]) -> Image.Image:
        asset_id = str(asset["id"])
        file_path = self._asset_file_path(asset)
        if not file_path.exists():
            raise VerticalImageWidgetError("Imagem ausente")

        mtime = file_path.stat().st_mtime
        cached = self._cache_by_asset_id.get(asset_id)
        if cached is not None and cached.mtime == mtime:
            return cached.image

        try:
            with Image.open(file_path) as image:
                source = image.convert("RGB")
        except OSError as exc:
            raise VerticalImageWidgetError("Falha ao ler imagem salva") from exc

        cache = VerticalImageCache(mtime=mtime, image=source)
        self._cache_by_asset_id[asset_id] = cache
        return cache.image

    def _build_viewport_frame(
        self,
        source: Image.Image,
        *,
        now_ms: int,
        scroll_speed_pps: int,
    ) -> tuple[Image.Image, int, int, int]:
        frame = Image.new("RGB", (self.frame_width, self.frame_height), (0, 0, 0))

        source_h = int(source.height)
        if source_h <= self.frame_height:
            y_offset = self.frame_height - source_h
            frame.paste(source, (0, y_offset))
            return frame, 0, 0, 0

        scroll_range_px = source_h - self.frame_height
        scroll_progress_px = int((now_ms * scroll_speed_pps) / 1000) % (scroll_range_px + 1)
        window_start_y = scroll_range_px - scroll_progress_px
        frame.paste(source, (0, -window_start_y))

        return frame, scroll_range_px, scroll_progress_px, window_start_y

    def _asset_public_payload(self, asset: dict[str, Any] | None) -> dict[str, Any] | None:
        if not isinstance(asset, dict):
            return None

        file_path = self._asset_file_path(asset)
        return {
            "id": asset["id"],
            "name": asset["name"],
            "original_name": asset["original_name"],
            "content_type": asset["content_type"],
            "active": bool(asset["active"]),
            "uploaded_at": asset["uploaded_at"],
            "updated_at": asset["updated_at"],
            "size_bytes": asset["size_bytes"],
            "width": asset["width"],
            "height": asset["height"],
            "revision": asset["revision"],
            "available": file_path.exists(),
            "raw_url": self._raw_url(asset_id=asset["id"]),
            "preview_url": self._raw_url(asset_id=asset["id"]),
        }

    def _asset_file_path(self, asset: dict[str, Any]) -> Path:
        storage_relpath = str(asset.get("storage_relpath") or self._storage_relpath(str(asset.get("id") or "")))
        return self.upload_dir / storage_relpath

    def _storage_relpath(self, asset_id: str) -> str:
        return f"{asset_id}.png"

    def _raw_url(self, *, asset_id: str | None = None) -> str:
        if asset_id is None:
            return "/widgets/vertical-image/raw"
        return f"/widgets/vertical-image/raw?asset_id={asset_id}"

    def _encode_frame_payload(self, image: Image.Image, image_mode: ImageMode) -> dict[str, Any]:
        if image_mode == "rgb_array":
            rgb_bytes = image.tobytes()
            pixels = [
                [rgb_bytes[index], rgb_bytes[index + 1], rgb_bytes[index + 2]]
                for index in range(0, len(rgb_bytes), 3)
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
        safe = Path(str(filename or "vertical_image.png")).name
        return safe or "vertical_image.png"

    def _clear_asset_files(self, asset: dict[str, Any] | None) -> None:
        if not isinstance(asset, dict):
            return

        file_path = self._asset_file_path(asset)
        if not file_path.exists():
            return

        try:
            file_path.unlink()
        except OSError:
            pass

    def _invalidate_cache(self, asset_id: str | None = None) -> None:
        if asset_id is None:
            self._cache_by_asset_id.clear()
            return
        self._cache_by_asset_id.pop(asset_id, None)

    def _normalize_scroll_speed(self, value: Any) -> int:
        try:
            speed = int(value)
        except (TypeError, ValueError):
            speed = self.default_scroll_speed_pps

        if speed < self.MIN_SCROLL_SPEED_PPS:
            return self.MIN_SCROLL_SPEED_PPS
        if speed > self.MAX_SCROLL_SPEED_PPS:
            return self.MAX_SCROLL_SPEED_PPS
        return speed
