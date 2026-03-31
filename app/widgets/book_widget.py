from __future__ import annotations

import asyncio
import json
from pathlib import Path
import time
from typing import Any

from app.services.image_service import ImageMode, ImageProcessor, ImageProcessingError
from app.services.skoob_service import SkoobSyncService
from app.widgets.base import BaseWidget


class BookWidget(BaseWidget):
    name = "book"

    def __init__(
        self,
        image_processor: ImageProcessor,
        state_path: Path,
        priority: int = 50,
        skoob_sync_service: SkoobSyncService | None = None,
        sync_interval_seconds: int = 0,
    ) -> None:
        super().__init__(priority=priority)
        self.image_processor = image_processor
        self.state_path = state_path
        self.skoob_sync_service = skoob_sync_service
        self.sync_interval_seconds = max(sync_interval_seconds, 0)
        self._last_sync_attempt_ts = 0.0
        self._sync_status: dict[str, Any] = {
            "last_attempt_ts": 0,
            "last_success_ts": 0,
            "last_error": "",
            "last_source": "",
            "last_is_reading": False,
        }
        self._ensure_state_file()
        self._bootstrap_sync_status()

    def get_state(self) -> dict[str, Any]:
        return self._load_state()

    def update_state(self, state_update: dict[str, Any]) -> dict[str, Any]:
        current = self._load_state()
        current.update(state_update)
        self._save_state(current)
        return current

    def sync_from_skoob(
        self,
        force: bool = True,
        profile_url: str | None = None,
        user_id: str | None = None,
        auth_cookie: str | None = None,
    ) -> dict[str, Any]:
        if self.skoob_sync_service is None:
            raise RuntimeError("Sincronizacao Skoob nao esta configurada.")

        now = time.time()
        if (
            not force
            and self.sync_interval_seconds > 0
            and now - self._last_sync_attempt_ts < self.sync_interval_seconds
        ):
            return self._load_state()

        self._last_sync_attempt_ts = now
        self._sync_status["last_attempt_ts"] = int(now)
        self._sync_status["last_error"] = ""
        try:
            synced_state = self.skoob_sync_service.sync(
                profile_url=profile_url,
                user_id=user_id,
                auth_cookie=auth_cookie,
            )
        except Exception as exc:
            self._sync_status["last_error"] = str(exc)
            raise

        self._save_state(synced_state)
        self._sync_status["last_success_ts"] = int(time.time())
        self._sync_status["last_source"] = str(synced_state.get("sync_source", ""))
        self._sync_status["last_is_reading"] = bool(synced_state.get("is_reading"))
        return synced_state

    def get_sync_status(self) -> dict[str, Any]:
        now = int(time.time())
        next_sync_ts = 0
        seconds_until_next_sync = 0
        is_configured = self._is_sync_configured()

        if (
            self.skoob_sync_service is not None
            and self.sync_interval_seconds > 0
            and self._last_sync_attempt_ts > 0
        ):
            next_sync_ts = int(self._last_sync_attempt_ts + self.sync_interval_seconds)
            seconds_until_next_sync = max(next_sync_ts - now, 0)

        state = self._load_state()
        return {
            "configured": is_configured,
            "auto_sync_enabled": is_configured and self.sync_interval_seconds > 0,
            "sync_interval_seconds": self.sync_interval_seconds,
            "last_attempt_ts": int(self._sync_status["last_attempt_ts"]),
            "last_success_ts": int(self._sync_status["last_success_ts"]),
            "last_error": str(self._sync_status["last_error"]),
            "last_source": str(self._sync_status["last_source"]),
            "last_is_reading": bool(self._sync_status["last_is_reading"]),
            "next_sync_ts": next_sync_ts,
            "seconds_until_next_sync": seconds_until_next_sync,
            "current_state": {
                "is_reading": bool(state.get("is_reading")),
                "title": str(state.get("title", "")),
                "author": str(state.get("author", "")),
                "cover_url": str(state.get("cover_url", "")),
                "sync_source": str(state.get("sync_source", "")),
                "profile_url": str(state.get("profile_url", "")),
                "last_sync_ts": self._to_int(state.get("last_sync_ts")),
            },
        }

    async def get_data(self, image_mode: ImageMode = "rgb565_base64") -> dict[str, Any] | None:
        await self._sync_if_due()
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

    async def _sync_if_due(self) -> None:
        if self.skoob_sync_service is None:
            return
        if self.sync_interval_seconds <= 0:
            return
        now = time.time()
        if now - self._last_sync_attempt_ts < self.sync_interval_seconds:
            return

        try:
            await asyncio.to_thread(self.sync_from_skoob, False, None, None, None)
        except Exception:
            return

    def _ensure_state_file(self) -> None:
        self.state_path.parent.mkdir(parents=True, exist_ok=True)
        if not self.state_path.exists():
            self._save_state(
                {
                    "is_reading": False,
                    "title": "",
                    "author": "",
                    "cover_url": "",
                    "sync_source": "manual",
                    "profile_url": "",
                    "last_sync_ts": 0,
                }
            )

    def _bootstrap_sync_status(self) -> None:
        state = self._load_state()
        last_sync_ts = self._to_int(state.get("last_sync_ts"))
        if last_sync_ts <= 0:
            return

        self._sync_status["last_success_ts"] = last_sync_ts
        self._sync_status["last_source"] = str(state.get("sync_source", ""))
        self._sync_status["last_is_reading"] = bool(state.get("is_reading"))

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
                "sync_source": "manual",
                "profile_url": "",
                "last_sync_ts": 0,
            }

    def _save_state(self, state: dict[str, Any]) -> None:
        self.state_path.write_text(
            json.dumps(state, ensure_ascii=False, separators=(",", ":")),
            encoding="utf-8",
        )

    def _to_int(self, value: Any) -> int:
        try:
            return int(str(value).strip())
        except (TypeError, ValueError):
            return 0

    def _is_sync_configured(self) -> bool:
        if self.skoob_sync_service is None:
            return False

        profile_url = str(self.skoob_sync_service.profile_url).strip()
        user_id = str(self.skoob_sync_service.user_id).strip()
        auth_cookie = str(self.skoob_sync_service.auth_cookie).strip()
        return bool(profile_url) or bool(user_id and auth_cookie)
