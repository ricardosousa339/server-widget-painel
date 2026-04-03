from typing import Any
from pathlib import Path
from PIL import Image, ImageOps, ImageSequence
from app.services.image_service import ImageMode
import json
import base64
import io
import time
from .models import GifPlaybackCache
from .exceptions import CustomGifWidgetError

class GifStateMixin:

    def _default_state(self) -> dict[str, Any]:
        return {
            "schema_version": self.SCHEMA_VERSION,
            "custom_assets": [],
            "doorbell_asset": None,
        }

    def _load_state(self) -> dict[str, Any]:
        state = self._normalize_state(self._read_state())
        if state.get("schema_version") != self.SCHEMA_VERSION or not self.state_path.exists():
            self._write_state(state)
        return state

    def _read_state(self) -> dict[str, Any]:
        for path in (self.state_path, self.legacy_state_path):
            if path == self.state_path or path.exists():
                try:
                    content = path.read_text(encoding="utf-8")
                    parsed = json.loads(content)
                    if isinstance(parsed, dict):
                        return parsed
                except (OSError, json.JSONDecodeError):
                    continue
        return self._default_state()

    def _write_state(self, state: dict[str, Any]) -> None:
        self.state_path.write_text(
            json.dumps(state, ensure_ascii=False, separators=(",", ":")),
            encoding="utf-8",
        )

    def _normalize_state(self, state: dict[str, Any]) -> dict[str, Any]:
        if not isinstance(state, dict):
            return self._default_state()

        if int(state.get("schema_version") or 0) != self.SCHEMA_VERSION:
            return self._migrate_legacy_state(state)

        normalized = self._default_state()
        custom_assets = state.get("custom_assets")
        if isinstance(custom_assets, list):
            normalized["custom_assets"] = [
                self._normalize_asset(asset, default_kind=self.KIND_CUSTOM)
                for asset in custom_assets
                if isinstance(asset, dict)
            ]

        doorbell_asset = state.get("doorbell_asset")
        if isinstance(doorbell_asset, dict):
            normalized["doorbell_asset"] = self._normalize_asset(
                doorbell_asset,
                default_kind=self.KIND_DOORBELL,
            )

        return normalized

    def _migrate_legacy_state(self, state: dict[str, Any]) -> dict[str, Any]:
        migrated = self._default_state()
        legacy_asset = self._legacy_asset_from_state(state)
        if legacy_asset is not None:
            migrated["custom_assets"] = [legacy_asset]
        return migrated

    def _legacy_asset_from_state(self, state: dict[str, Any]) -> dict[str, Any] | None:
        original_name = str(state.get("original_name") or "").strip()
        size_bytes = int(state.get("size_bytes") or 0)
        frame_count = int(state.get("frame_count") or 0)
        total_duration_ms = int(state.get("total_duration_ms") or 0)
        if not original_name and not size_bytes and not frame_count and not total_duration_ms:
            return None

        legacy_file = self.legacy_upload_path
        if not legacy_file.exists():
            return None

        migrated_relpath = self._storage_relpath(self.KIND_CUSTOM, "legacy-custom-gif")
        migrated_path = self.upload_dir / migrated_relpath
        migrated_path.parent.mkdir(parents=True, exist_ok=True)
        if not migrated_path.exists():
            try:
                shutil.copy2(legacy_file, migrated_path)
            except OSError:
                return None

        now = int(time.time())
        return {
            "id": "legacy-custom-gif",
            "kind": self.KIND_CUSTOM,
            "name": original_name or "custom.gif",
            "original_name": original_name or "custom.gif",
            "content_type": str(state.get("content_type") or "image/gif"),
            "storage_relpath": migrated_relpath,
            "active": True,
            "uploaded_at": int(state.get("uploaded_at") or now),
            "updated_at": now,
            "size_bytes": size_bytes,
            "frame_count": frame_count,
            "total_duration_ms": total_duration_ms,
            "width": self.frame_width,
            "height": self.frame_height,
            "revision": 1,
        }

    def _normalize_asset(self, asset: dict[str, Any], *, default_kind: str) -> dict[str, Any]:
        normalized_kind = self._normalize_kind(str(asset.get("kind") or default_kind))
        asset_id = str(asset.get("id") or uuid.uuid4().hex)
        storage_relpath = str(
            asset.get("storage_relpath")
            or asset.get("storage_path")
            or self._storage_relpath(normalized_kind, asset_id)
        )
        name = str(asset.get("name") or asset.get("original_name") or f"{asset_id}.gif")
        original_name = str(asset.get("original_name") or name)

        return {
            "id": asset_id,
            "kind": normalized_kind,
            "name": name,
            "original_name": original_name,
            "content_type": str(asset.get("content_type") or "image/gif"),
            "storage_relpath": storage_relpath,
            "active": bool(asset.get("active", True if normalized_kind == self.KIND_CUSTOM else True)),
            "uploaded_at": int(asset.get("uploaded_at") or 0),
            "updated_at": int(asset.get("updated_at") or asset.get("uploaded_at") or 0),
            "size_bytes": int(asset.get("size_bytes") or 0),
            "frame_count": int(asset.get("frame_count") or 0),
            "total_duration_ms": int(asset.get("total_duration_ms") or 0),
            "width": int(asset.get("width") or self.frame_width),
            "height": int(asset.get("height") or self.frame_height),
            "revision": max(1, int(asset.get("revision") or 1)),
        }

    def _normalize_kind(self, kind: str) -> str:
        normalized = str(kind or self.KIND_CUSTOM).strip().lower()
        if normalized not in {self.KIND_CUSTOM, self.KIND_DOORBELL}:
            raise CustomGifWidgetError("Tipo de GIF invalido")
        return normalized

    def _find_asset(self, state: dict[str, Any], asset_id: str) -> dict[str, Any] | None:
        if state["doorbell_asset"] and str(state["doorbell_asset"].get("id")) == asset_id:
            return state["doorbell_asset"]

        for asset in state["custom_assets"]:
            if str(asset.get("id")) == asset_id:
                return asset
        return None

    def _remove_asset(self, state: dict[str, Any], asset_id: str) -> dict[str, Any] | None:
        doorbell_asset = state["doorbell_asset"]
        if isinstance(doorbell_asset, dict) and str(doorbell_asset.get("id")) == asset_id:
            state["doorbell_asset"] = None
            return doorbell_asset

        for index, asset in enumerate(state["custom_assets"]):
            if str(asset.get("id")) == asset_id:
                return state["custom_assets"].pop(index)

        return None

    def _asset_file_path(self, asset: dict[str, Any]) -> Path:
        storage_relpath = str(asset.get("storage_relpath") or "")
        if not storage_relpath:
            storage_relpath = self._storage_relpath(str(asset.get("kind") or self.KIND_CUSTOM), str(asset.get("id") or ""))
        return self.upload_dir / storage_relpath

    def _storage_relpath(self, kind: str, asset_id: str) -> str:
        normalized_kind = self._normalize_kind(kind)
        if normalized_kind == self.KIND_DOORBELL:
            return f"doorbell_gif/{asset_id}.gif"
        return f"custom_gifs/{asset_id}.gif"

    def _asset_public_payload(self, asset: dict[str, Any] | None) -> dict[str, Any] | None:
        if not isinstance(asset, dict):
            return None

        file_path = self._asset_file_path(asset)
        exists = file_path.exists()
        return {
            "id": asset["id"],
            "kind": asset["kind"],
            "name": asset["name"],
            "original_name": asset["original_name"],
            "content_type": asset["content_type"],
            "active": bool(asset["active"]),
            "uploaded_at": asset["uploaded_at"],
            "updated_at": asset["updated_at"],
            "size_bytes": asset["size_bytes"],
            "frame_count": asset["frame_count"],
            "total_duration_ms": asset["total_duration_ms"],
            "width": asset["width"],
            "height": asset["height"],
            "revision": asset["revision"],
            "available": exists,
            "raw_url": self._raw_url(kind=asset["kind"], asset_id=asset["id"]),
            "playback_url": self._playback_url(kind=asset["kind"], asset_id=asset["id"]),
            "preview_url": self._raw_url(kind=asset["kind"], asset_id=asset["id"]),
        }

    def _raw_url(self, *, kind: str | None = None, asset_id: str | None = None) -> str:
        query: list[str] = []
        if kind is not None:
            query.append(f"kind={kind}")
        if asset_id is not None:
            query.append(f"asset_id={asset_id}")
        suffix = ""
        if query:
            suffix = "?" + "&".join(query)
        return f"/widgets/custom-gif/raw{suffix}"

    def _playback_url(
        self,
        *,
        kind: str | None = None,
        asset_id: str | None = None,
        playhead_ms: int | None = None,
    ) -> str:
        query: list[str] = []
        if kind is not None:
            query.append(f"kind={kind}")
        if asset_id is not None:
            query.append(f"asset_id={asset_id}")
        if playhead_ms is not None:
            query.append(f"playhead_ms={int(playhead_ms)}")
        suffix = ""
        if query:
            suffix = "?" + "&".join(query)
        return f"/widgets/custom-gif/playback{suffix}"

    def _sanitize_filename(self, filename: str) -> str:
        safe = Path(str(filename or "custom.gif")).name
        return safe or "custom.gif"


class GifProcessorMixin:

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

    def _ensure_cache_for_asset(self, asset: dict[str, Any]) -> GifPlaybackCache:
        asset_id = str(asset["id"])
        file_path = self._asset_file_path(asset)
        if not file_path.exists():
            raise CustomGifWidgetError("GIF ausente")

        mtime = file_path.stat().st_mtime
        cached = self._cache_by_asset_id.get(asset_id)
        if cached is not None and cached.mtime == mtime:
            return cached

        cache = self._build_cache_from_file(file_path)
        self._cache_by_asset_id[asset_id] = cache
        return cache

    def _ensure_cache_from_path(self, file_path: Path) -> GifPlaybackCache:
        return self._build_cache_from_file(file_path)

    def _build_cache_from_file(self, file_path: Path) -> GifPlaybackCache:
        try:
            with Image.open(file_path) as image:
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

        return GifPlaybackCache(
            mtime=file_path.stat().st_mtime,
            frames=frames,
            durations_ms=durations_ms,
            total_duration_ms=max(1, total_ms),
        )

    def _frame_index_for_playhead(self, durations_ms: list[int], playhead_ms: int) -> int:
        if not durations_ms:
            return 0

        if len(durations_ms) == 1:
            return 0

        total_ms = max(1, sum(max(1, duration) for duration in durations_ms))
        phase = playhead_ms % total_ms

        acc = 0
        for index, duration in enumerate(durations_ms):
            acc += max(1, duration)
            if phase < acc:
                return index

        return len(durations_ms) - 1

    def _normalize_playhead_ms(
        self,
        *,
        playhead_ms: int | None,
        fallback_ms: int,
        total_duration_ms: int,
    ) -> int:
        base = fallback_ms if playhead_ms is None else int(playhead_ms)
        if total_duration_ms <= 0:
            return max(0, base)
        return max(0, base % total_duration_ms)

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
