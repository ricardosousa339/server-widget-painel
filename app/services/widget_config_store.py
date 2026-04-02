from __future__ import annotations

import json
from pathlib import Path
import time
from typing import Any, Iterable


class WidgetConfigStore:
    def __init__(self, state_path: Path, available_widgets: Iterable[str]) -> None:
        self.state_path = state_path
        self.available_widgets = self._normalize_names(available_widgets)
        self._ensure_state_file()

    def get_state(self) -> dict[str, Any]:
        state = self._normalize_state(self._read_state())
        return {
            "available_widgets": list(self.available_widgets),
            "enabled_widgets": list(state["enabled_widgets"]),
            "updated_at": state["updated_at"],
        }

    def update_enabled_widgets(self, enabled_widgets: Iterable[str]) -> dict[str, Any]:
        normalized_enabled = self._normalize_names(enabled_widgets)
        valid_enabled = [name for name in normalized_enabled if name in self.available_widgets]
        state = {
            "enabled_widgets": valid_enabled,
            "updated_at": int(time.time()),
        }
        self._write_state(state)
        return self.get_state()

    def enabled_set(self) -> set[str]:
        return set(self.get_state()["enabled_widgets"])

    def _default_state(self) -> dict[str, Any]:
        return {
            "enabled_widgets": list(self.available_widgets),
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

        return {
            "enabled_widgets": enabled,
            "updated_at": updated_at,
        }

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