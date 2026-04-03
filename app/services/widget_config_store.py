from __future__ import annotations

import json
from pathlib import Path
import time
from typing import Any, Iterable


class WidgetConfigStore:
    DEFAULT_DISPLAY_MODE = "priority"
    DEFAULT_HYBRID_PERIOD_SECONDS = 300
    DEFAULT_GIF_DURATION_SECONDS = 30
    MIN_HYBRID_PERIOD_SECONDS = 10
    MAX_HYBRID_PERIOD_SECONDS = 86400
    MIN_GIF_DURATION_SECONDS = 1
    MAX_GIF_DURATION_SECONDS = 3600
    ALLOWED_DISPLAY_MODES = {"priority", "custom_only", "hybrid"}

    def __init__(self, state_path: Path, available_widgets: Iterable[str]) -> None:
        self.state_path = state_path
        self.available_widgets = self._normalize_names(available_widgets)
        self._ensure_state_file()

    def get_state(self) -> dict[str, Any]:
        state = self._normalize_state(self._read_state())
        return {
            "available_widgets": list(self.available_widgets),
            "enabled_widgets": list(state["enabled_widgets"]),
            "display_mode": state["display_mode"],
            "hybrid_period_seconds": state["hybrid_period_seconds"],
            "default_gif_duration_seconds": state["default_gif_duration_seconds"],
            "updated_at": state["updated_at"],
        }

    def update_enabled_widgets(self, enabled_widgets: Iterable[str]) -> dict[str, Any]:
        return self.update_config(enabled_widgets=enabled_widgets)

    def update_config(
        self,
        *,
        enabled_widgets: Iterable[str] | None = None,
        display_mode: str | None = None,
        hybrid_period_seconds: int | None = None,
        default_gif_duration_seconds: int | None = None,
    ) -> dict[str, Any]:
        current = self._normalize_state(self._read_state())

        if enabled_widgets is None:
            valid_enabled = list(current["enabled_widgets"])
        else:
            normalized_enabled = self._normalize_names(enabled_widgets)
            valid_enabled = [name for name in normalized_enabled if name in self.available_widgets]

        normalized_mode = self._normalize_display_mode(
            current["display_mode"] if display_mode is None else display_mode
        )
        normalized_period = self._normalize_int(
            hybrid_period_seconds,
            default=current["hybrid_period_seconds"],
            min_value=self.MIN_HYBRID_PERIOD_SECONDS,
            max_value=self.MAX_HYBRID_PERIOD_SECONDS,
        )
        normalized_show = self._normalize_int(
            default_gif_duration_seconds,
            default=current["default_gif_duration_seconds"],
            min_value=self.MIN_GIF_DURATION_SECONDS,
            max_value=self.MAX_GIF_DURATION_SECONDS,
        )

        if normalized_show >= normalized_period:
            normalized_show = max(
                self.MIN_GIF_DURATION_SECONDS,
                normalized_period - 1,
            )

        state = {
            "enabled_widgets": valid_enabled,
            "display_mode": normalized_mode,
            "hybrid_period_seconds": normalized_period,
            "default_gif_duration_seconds": normalized_show,
            "updated_at": int(time.time()),
        }
        self._write_state(state)
        return self.get_state()

    def enabled_set(self) -> set[str]:
        return set(self.get_state()["enabled_widgets"])

    def _default_state(self) -> dict[str, Any]:
        return {
            "enabled_widgets": list(self.available_widgets),
            "display_mode": self.DEFAULT_DISPLAY_MODE,
            "hybrid_period_seconds": self.DEFAULT_HYBRID_PERIOD_SECONDS,
            "default_gif_duration_seconds": self.DEFAULT_GIF_DURATION_SECONDS,
            "updated_at": int(time.time()),
        }

    def _ensure_state_file(self) -> None:
        self.state_path.parent.mkdir(parents=True, exist_ok=True)
        if not self.state_path.exists():
            self._write_state(self._default_state())
            return

        normalized = self._normalize_state(self._read_state())
        self._write_state(normalized)

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
        enabled_raw = state.get("enabled_widgets")
        if not isinstance(enabled_raw, list):
            enabled_raw = list(self.available_widgets)

        enabled = self._normalize_names(enabled_raw)
        enabled = [name for name in enabled if name in self.available_widgets]

        updated_at_raw = state.get("updated_at")
        try:
            updated_at = int(updated_at_raw)
        except (TypeError, ValueError):
            updated_at = int(time.time())

        display_mode = self._normalize_display_mode(state.get("display_mode"))

        hybrid_period_seconds = self._normalize_int(
            state.get("hybrid_period_seconds"),
            default=self.DEFAULT_HYBRID_PERIOD_SECONDS,
            min_value=self.MIN_HYBRID_PERIOD_SECONDS,
            max_value=self.MAX_HYBRID_PERIOD_SECONDS,
        )
        default_gif_duration_seconds = self._normalize_int(
            state.get("default_gif_duration_seconds"),
            default=self.DEFAULT_GIF_DURATION_SECONDS,
            min_value=self.MIN_GIF_DURATION_SECONDS,
            max_value=self.MAX_GIF_DURATION_SECONDS,
        )

        if default_gif_duration_seconds >= hybrid_period_seconds:
            default_gif_duration_seconds = max(
                self.MIN_GIF_DURATION_SECONDS,
                hybrid_period_seconds - 1,
            )

        return {
            "enabled_widgets": enabled,
            "display_mode": display_mode,
            "hybrid_period_seconds": hybrid_period_seconds,
            "default_gif_duration_seconds": default_gif_duration_seconds,
            "updated_at": updated_at,
        }

    def _normalize_display_mode(self, value: Any) -> str:
        mode = str(value or "").strip().lower()
        if mode not in self.ALLOWED_DISPLAY_MODES:
            return self.DEFAULT_DISPLAY_MODE
        return mode

    @staticmethod
    def _normalize_int(value: Any, *, default: int, min_value: int, max_value: int) -> int:
        try:
            parsed = int(value)
        except (TypeError, ValueError):
            parsed = default

        if parsed < min_value:
            return min_value
        if parsed > max_value:
            return max_value
        return parsed

    @staticmethod
    def _normalize_names(values: Iterable[str]) -> list[str]:
        normalized: list[str] = []
        for value in values:
            if not isinstance(value, str):
                continue
            name = value.strip().lower()
            if not name:
                continue
            if name not in normalized:
                normalized.append(name)
        return normalized