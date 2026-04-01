from __future__ import annotations

import asyncio
import time
from typing import Any, Awaitable, Callable


class ScreenPayloadCache:
    def __init__(
        self,
        fetch_payload: Callable[[], Awaitable[dict[str, Any]]],
        refresh_interval_ms: int = 1500,
    ) -> None:
        self._fetch_payload = fetch_payload
        self.refresh_interval_ms = max(100, int(refresh_interval_ms))

        self._lock = asyncio.Lock()
        self._payload: dict[str, Any] | None = None
        self._last_refresh_monotonic_ms: int | None = None

    async def get_payload(self, force_refresh: bool = False) -> dict[str, Any]:
        now_ms = self._now_ms()

        if not force_refresh and self._is_fresh(now_ms):
            assert self._payload is not None
            return self._payload

        async with self._lock:
            now_ms = self._now_ms()
            if not force_refresh and self._is_fresh(now_ms):
                assert self._payload is not None
                return self._payload

            try:
                payload = await self._fetch_payload()
            except Exception:
                if self._payload is not None:
                    # Em falha temporaria, mantém ultimo payload para fluidez da animacao.
                    return self._payload
                raise

            self._payload = payload
            self._last_refresh_monotonic_ms = self._now_ms()
            return payload

    def age_ms(self) -> int:
        if self._last_refresh_monotonic_ms is None:
            return 0
        return max(0, self._now_ms() - self._last_refresh_monotonic_ms)

    def _is_fresh(self, now_ms: int) -> bool:
        if self._payload is None or self._last_refresh_monotonic_ms is None:
            return False
        return (now_ms - self._last_refresh_monotonic_ms) < self.refresh_interval_ms

    def _now_ms(self) -> int:
        return int(time.monotonic() * 1000)
