from __future__ import annotations

import base64
import io
import json
import shutil
import time
import uuid
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from PIL import Image, ImageOps, ImageSequence

from app.services.image_service import ImageMode
from app.widgets.base import BaseWidget
from app.widgets.custom_gif.mixins import GifStateMixin, GifProcessorMixin
from app.widgets.custom_gif.models import GifPlaybackCache
from app.widgets.custom_gif.exceptions import CustomGifWidgetError



class CustomGifWidget(BaseWidget, GifStateMixin, GifProcessorMixin):
    name = "custom_gif"
    SCHEMA_VERSION = 2
    KIND_CUSTOM = "custom"
    KIND_DOORBELL = "doorbell"
    ACTIVE_ASSET_ROTATION_SLOT_MS = 5000

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
        self.custom_upload_dir = self.upload_dir / "custom_gifs"
        self.doorbell_upload_dir = self.upload_dir / "doorbell_gif"
        self.legacy_state_path = (
            self.state_path
            if self.state_path.name == "custom_gif_state.json"
            else self.state_path.with_name("custom_gif_state.json")
        )
        self.legacy_upload_path = self.upload_dir / "custom.gif"
        self.frame_width = frame_width
        self.frame_height = frame_height
        self.max_upload_bytes = max_upload_bytes

        self._cache_by_asset_id: dict[str, GifPlaybackCache] = {}

        self._ensure_paths()

    async def get_data(
        self,
        image_mode: ImageMode = "rgb565_base64",
        *,
        kind: str = KIND_CUSTOM,
        asset_id: str | None = None,
        playhead_ms: int | None = None,
        allow_fallback: bool = True,
    ) -> dict[str, Any] | None:
        try:
            selection = self._resolve_selection(
                kind=kind,
                asset_id=asset_id,
                playhead_ms=playhead_ms,
                allow_fallback=allow_fallback,
            )
            if selection is None:
                return None

            asset = selection["asset"]
            cache = self._ensure_cache_for_asset(asset)
            if not cache.frames:
                return None

            playhead_value = self._normalize_playhead_ms(
                playhead_ms=playhead_ms,
                fallback_ms=selection["playhead_ms"],
                total_duration_ms=cache.total_duration_ms,
            )
            frame_index = self._frame_index_for_playhead(cache.durations_ms, playhead_value)
            frame = cache.frames[frame_index]
        except CustomGifWidgetError:
            return None

        return {
            "widget": self.name,
            "priority": self.priority,
            "ts": int(time.time()),
            "data": {
                "requested_kind": kind,
                "asset_kind": asset["kind"],
                "asset_id": asset["id"],
                "asset_name": asset["name"],
                "asset_revision": asset["revision"],
                "asset_active": bool(asset["active"]),
                "frame_index": frame_index,
                "frame_count": len(cache.frames),
                "total_duration_ms": cache.total_duration_ms,
                "playhead_ms": playhead_value,
                "selected_index": selection["selected_index"],
                "selected_count": selection["active_count"],
                "cycle_total_ms": selection["cycle_total_ms"],
                "cycle_position_ms": selection["cycle_position_ms"],
                "raw_url": self._raw_url(kind=asset["kind"], asset_id=asset["id"]),
                "preview_url": self._raw_url(kind=asset["kind"], asset_id=asset["id"]),
                "playback_url": self._playback_url(
                    kind=asset["kind"],
                    asset_id=asset["id"],
                    playhead_ms=playhead_value,
                ),
                "frame": self._encode_frame_payload(frame, image_mode=image_mode),
            },
        }

    def get_state(self) -> dict[str, Any]:
        state = self._load_state()
        custom_assets = [self._asset_public_payload(asset) for asset in state["custom_assets"]]
        doorbell_asset = state["doorbell_asset"]
        selected = self._resolve_selection(kind=self.KIND_CUSTOM)
        selected_asset = selected["asset"] if selected is not None else None

        custom_cycle_total_ms = selected["cycle_total_ms"] if selected is not None else 0
        custom_cycle_position_ms = selected["cycle_position_ms"] if selected is not None else 0

        return {
            "schema_version": self.SCHEMA_VERSION,
            "max_upload_bytes": self.max_upload_bytes,
            "custom": {
                "assets": custom_assets,
                "active_count": sum(1 for asset in custom_assets if asset["active"]),
                "selected_asset": self._asset_public_payload(selected_asset) if selected_asset else None,
                "selected_asset_id": selected_asset["id"] if selected_asset else None,
                "cycle_total_ms": custom_cycle_total_ms,
                "cycle_position_ms": custom_cycle_position_ms,
                "playback_url": self._playback_url(
                    kind=self.KIND_CUSTOM,
                    asset_id=selected_asset["id"] if selected_asset else None,
                ),
                "raw_url": self._raw_url(kind=self.KIND_CUSTOM),
            },
            "doorbell": {
                "asset": self._asset_public_payload(doorbell_asset) if doorbell_asset else None,
                "configured": bool(doorbell_asset and doorbell_asset["active"]),
                "playback_url": self._playback_url(
                    kind=self.KIND_DOORBELL,
                    asset_id=doorbell_asset["id"] if isinstance(doorbell_asset, dict) else None,
                ),
                "raw_url": self._raw_url(
                    kind=self.KIND_DOORBELL,
                    asset_id=doorbell_asset["id"] if isinstance(doorbell_asset, dict) else None,
                ),
            },
        }

    def save_gif(
        self,
        *,
        filename: str,
        content_type: str,
        raw_bytes: bytes,
        kind: str = KIND_CUSTOM,
        active: bool = True,
    ) -> dict[str, Any]:
        if not raw_bytes:
            raise CustomGifWidgetError("Arquivo vazio")

        if len(raw_bytes) > self.max_upload_bytes:
            raise CustomGifWidgetError(
                f"Arquivo muito grande (limite {self.max_upload_bytes} bytes)"
            )

        asset_kind = self._normalize_kind(kind)
        safe_name = self._sanitize_filename(filename)

        self._validate_gif(raw_bytes)

        asset_id = uuid.uuid4().hex
        storage_relpath = self._storage_relpath(asset_kind, asset_id)
        file_path = self.upload_dir / storage_relpath
        file_path.parent.mkdir(parents=True, exist_ok=True)
        file_path.write_bytes(raw_bytes)

        cache = self._ensure_cache_from_path(file_path)
        now = int(time.time())
        asset = {
            "id": asset_id,
            "kind": asset_kind,
            "name": safe_name,
            "original_name": safe_name,
            "content_type": content_type or "image/gif",
            "storage_relpath": storage_relpath,
            "active": bool(active),
            "uploaded_at": now,
            "updated_at": now,
            "size_bytes": len(raw_bytes),
            "frame_count": len(cache.frames),
            "total_duration_ms": cache.total_duration_ms,
            "width": self.frame_width,
            "height": self.frame_height,
            "revision": 1,
        }

        state = self._load_state()
        if asset_kind == self.KIND_DOORBELL:
            previous_asset = state.get("doorbell_asset")
            self._clear_asset_files(previous_asset)
            if isinstance(previous_asset, dict):
                self._invalidate_cache(str(previous_asset.get("id") or ""))
            state["doorbell_asset"] = asset
        else:
            state["custom_assets"].append(asset)

        self._cache_by_asset_id[asset_id] = cache
        self._write_state(state)
        return self.get_state()

    def update_asset(self, asset_id: str, *, active: bool | None = None) -> dict[str, Any]:
        state = self._load_state()
        asset = self._find_asset(state, asset_id)
        if asset is None:
            raise CustomGifWidgetError("GIF nao encontrado")

        changed = False
        if active is not None:
            asset["active"] = bool(active)
            changed = True

        if changed:
            asset["updated_at"] = int(time.time())
            asset["revision"] = max(1, int(asset.get("revision") or 1)) + 1
            self._write_state(state)

        return self.get_state()

    def delete_asset(self, asset_id: str) -> dict[str, Any]:
        state = self._load_state()
        removed = self._remove_asset(state, asset_id)
        if removed is None:
            raise CustomGifWidgetError("GIF nao encontrado")

        self._clear_asset_files(removed)
        self._invalidate_cache(asset_id)
        self._write_state(state)
        return self.get_state()

    def clear_gif(self, kind: str = KIND_CUSTOM) -> dict[str, Any]:
        state = self._load_state()
        normalized_kind = self._normalize_kind(kind)

        if normalized_kind == self.KIND_DOORBELL:
            doorbell_asset = state.get("doorbell_asset")
            self._clear_asset_files(doorbell_asset)
            if isinstance(doorbell_asset, dict):
                self._invalidate_cache(str(doorbell_asset.get("id") or ""))
            state["doorbell_asset"] = None
        else:
            for asset in state["custom_assets"]:
                self._clear_asset_files(asset)
                self._invalidate_cache(asset["id"])
            state["custom_assets"] = []

        self._write_state(state)
        return self.get_state()

    def raw_file_path(self, *, kind: str = KIND_CUSTOM, asset_id: str | None = None) -> Path | None:
        selection = self._resolve_selection(kind=kind, asset_id=asset_id, allow_fallback=True)
        if selection is None:
            return None
        return self._asset_file_path(selection["asset"])

    def playback_package(
        self,
        *,
        kind: str = KIND_CUSTOM,
        asset_id: str | None = None,
        playhead_ms: int | None = None,
    ) -> dict[str, Any] | None:
        try:
            selection = self._resolve_selection(
                kind=kind,
                asset_id=asset_id,
                playhead_ms=playhead_ms,
                allow_fallback=True,
            )
            if selection is None:
                return None

            asset = selection["asset"]
            cache = self._ensure_cache_for_asset(asset)
            if not cache.frames:
                return None

            playhead_value = self._normalize_playhead_ms(
                playhead_ms=playhead_ms,
                fallback_ms=selection["playhead_ms"],
                total_duration_ms=cache.total_duration_ms,
            )

            frames = []
            for index, (frame, duration_ms) in enumerate(zip(cache.frames, cache.durations_ms, strict=False)):
                frames.append(
                    {
                        "index": index,
                        "duration_ms": duration_ms,
                        "frame": self._encode_frame_payload(frame, image_mode="rgb565_base64"),
                    }
                )
        except CustomGifWidgetError:
            return None

        return {
            "widget": self.name,
            "priority": self.priority,
            "ts": int(time.time()),
            "data": {
                "requested_kind": kind,
                "asset_kind": asset["kind"],
                "asset_id": asset["id"],
                "asset_name": asset["name"],
                "asset_revision": asset["revision"],
                "asset_active": bool(asset["active"]),
                "width": self.frame_width,
                "height": self.frame_height,
                "frame_count": len(cache.frames),
                "total_duration_ms": cache.total_duration_ms,
                "playhead_ms": playhead_value,
                "selected_index": selection["selected_index"],
                "selected_count": selection["active_count"],
                "cycle_total_ms": selection["cycle_total_ms"],
                "cycle_position_ms": selection["cycle_position_ms"],
                "raw_url": self._raw_url(kind=asset["kind"], asset_id=asset["id"]),
                "preview_url": self._raw_url(kind=asset["kind"], asset_id=asset["id"]),
                "playback_url": self._playback_url(
                    kind=asset["kind"],
                    asset_id=asset["id"],
                    playhead_ms=playhead_value,
                ),
                "frames": frames,
            },
        }

    def _ensure_paths(self) -> None:
        self.state_path.parent.mkdir(parents=True, exist_ok=True)
        self.upload_dir.mkdir(parents=True, exist_ok=True)
        self.custom_upload_dir.mkdir(parents=True, exist_ok=True)
        self.doorbell_upload_dir.mkdir(parents=True, exist_ok=True)

    def _clear_asset_files(self, asset: dict[str, Any] | None) -> None:
        if not isinstance(asset, dict):
            return

        file_path = self._asset_file_path(asset)
        if file_path.exists():
            try:
                file_path.unlink()
            except OSError:
                pass

    def _invalidate_cache(self, asset_id: str | None = None) -> None:
        if asset_id is None:
            self._cache_by_asset_id.clear()
            return
        self._cache_by_asset_id.pop(asset_id, None)

    def _resolve_selection(
        self,
        *,
        kind: str,
        asset_id: str | None = None,
        playhead_ms: int | None = None,
        allow_fallback: bool = True,
    ) -> dict[str, Any] | None:
        normalized_kind = self._normalize_kind(kind)
        state = self._load_state()
        now_ms = int(time.time() * 1000)

        if normalized_kind == self.KIND_DOORBELL:
            doorbell_asset = state["doorbell_asset"]
            if isinstance(doorbell_asset, dict) and doorbell_asset.get("active", True):
                try:
                    cache = self._ensure_cache_for_asset(doorbell_asset)
                except CustomGifWidgetError:
                    if allow_fallback:
                        fallback = self._resolve_custom_selection(
                            state,
                            asset_id=asset_id,
                            playhead_ms=playhead_ms,
                            allow_inactive_fallback=True,
                            now_ms=now_ms,
                        )
                        if fallback is not None:
                            fallback["requested_kind"] = self.KIND_DOORBELL
                            return fallback
                    return None

                selected_playhead = self._normalize_playhead_ms(
                    playhead_ms=playhead_ms,
                    fallback_ms=0,
                    total_duration_ms=cache.total_duration_ms,
                )
                return {
                    "asset": doorbell_asset,
                    "active_count": 1,
                    "selected_index": 0,
                    "cycle_total_ms": cache.total_duration_ms,
                    "cycle_position_ms": selected_playhead,
                    "playhead_ms": selected_playhead,
                }

            if allow_fallback:
                fallback = self._resolve_custom_selection(state, asset_id=asset_id, allow_inactive_fallback=True)
                if fallback is not None:
                    fallback["requested_kind"] = self.KIND_DOORBELL
                    return fallback

            return None

        return self._resolve_custom_selection(
            state,
            asset_id=asset_id,
            playhead_ms=playhead_ms,
            allow_inactive_fallback=False,
            now_ms=now_ms,
        )

    def _resolve_custom_selection(
        self,
        state: dict[str, Any],
        *,
        asset_id: str | None = None,
        playhead_ms: int | None = None,
        allow_inactive_fallback: bool,
        now_ms: int | None = None,
    ) -> dict[str, Any] | None:
        assets = [asset for asset in state["custom_assets"] if isinstance(asset, dict)]
        if not assets:
            return None

        assets = sorted(
            assets,
            key=lambda asset: (
                int(asset.get("uploaded_at") or 0),
                str(asset.get("name") or ""),
                str(asset.get("id") or ""),
            ),
        )

        if asset_id is not None:
            selected_index = next(
                (index for index, asset in enumerate(assets) if str(asset.get("id")) == asset_id),
                None,
            )
            if selected_index is None:
                return None

            asset = assets[selected_index]
            try:
                cache = self._ensure_cache_for_asset(asset)
            except CustomGifWidgetError:
                return None
            selected_playhead = self._normalize_playhead_ms(
                playhead_ms=playhead_ms,
                fallback_ms=0 if now_ms is None else now_ms,
                total_duration_ms=cache.total_duration_ms,
            )
            return {
                "asset": asset,
                "active_count": 1,
                "selected_index": selected_index,
                "cycle_total_ms": cache.total_duration_ms,
                "cycle_position_ms": selected_playhead,
                "playhead_ms": selected_playhead,
            }

        active_assets = [asset for asset in assets if bool(asset.get("active", True))]
        if not active_assets and allow_inactive_fallback:
            active_assets = assets[:]

        if not active_assets:
            return None

        active_assets = sorted(
            active_assets,
            key=lambda asset: (
                int(asset.get("uploaded_at") or 0),
                str(asset.get("name") or ""),
                str(asset.get("id") or ""),
            ),
        )
        available_assets: list[tuple[dict[str, Any], GifPlaybackCache]] = []
        for asset in active_assets:
            try:
                cache = self._ensure_cache_for_asset(asset)
            except CustomGifWidgetError:
                continue
            available_assets.append((asset, cache))

        if not available_assets:
            return None

        slot_ms = max(1, self.ACTIVE_ASSET_ROTATION_SLOT_MS)
        cycle_total_ms = slot_ms * len(available_assets)
        phase = (now_ms if now_ms is not None else int(time.time() * 1000)) % cycle_total_ms
        selected_index = min(phase // slot_ms, len(available_assets) - 1)
        asset, _cache = available_assets[selected_index]
        asset_phase_ms = phase - (selected_index * slot_ms)

        return {
            "asset": asset,
            "active_count": len(available_assets),
            "selected_index": selected_index,
            "cycle_total_ms": cycle_total_ms,
            "cycle_position_ms": phase,
            "playhead_ms": asset_phase_ms,
        }
