from __future__ import annotations

import time
from typing import Any

import requests
import spotipy
from spotipy.oauth2 import SpotifyOAuth

from app.config import Settings
from app.services.image_service import ImageMode, ImageProcessor, ImageProcessingError
from app.widgets.base import BaseWidget


class SpotifyWidget(BaseWidget):
    name = "spotify"

    def __init__(
        self,
        settings: Settings,
        image_processor: ImageProcessor,
        priority: int = 100,
    ) -> None:
        super().__init__(priority=priority)
        self.settings = settings
        self.image_processor = image_processor

        self._client_id = settings.spotify_client_id
        self._client_secret = settings.spotify_client_secret
        self._redirect_uri = settings.spotify_redirect_uri
        self._refresh_token = settings.spotify_refresh_token
        self._access_token = settings.spotify_access_token

        self._oauth_manager = self._build_oauth_manager()

    async def get_data(self, image_mode: ImageMode = "rgb565_base64") -> dict[str, Any] | None:
        client = self._get_client()
        if client is None:
            return None

        try:
            playing = client.current_user_playing_track()
        except (spotipy.SpotifyException, requests.RequestException):
            return None

        if not playing or not playing.get("is_playing"):
            return None

        item = playing.get("item") or {}
        album = item.get("album") or {}
        artists = item.get("artists") or []

        payload: dict[str, Any] = {
            "widget": self.name,
            "priority": self.priority,
            "ts": int(time.time()),
            "data": {
                "currently_playing": True,
                "track": item.get("name", ""),
                "artist": ", ".join(artist.get("name", "") for artist in artists),
                "album": album.get("name", ""),
                "progress_ms": playing.get("progress_ms", 0),
                "duration_ms": item.get("duration_ms", 0),
            },
        }

        images = album.get("images") or []
        if images:
            image_url = images[0].get("url")
            if image_url:
                try:
                    payload["data"]["cover"] = self.image_processor.process_from_url(
                        image_url,
                        image_mode=image_mode,
                    )
                except ImageProcessingError:
                    payload["data"]["cover"] = None

        return payload

    def _build_oauth_manager(self) -> SpotifyOAuth | None:
        if not (self._client_id and self._client_secret and self._redirect_uri):
            return None

        return SpotifyOAuth(
            client_id=self._client_id,
            client_secret=self._client_secret,
            redirect_uri=self._redirect_uri,
            scope="user-read-currently-playing user-read-playback-state",
            open_browser=False,
        )

    def _refresh_access_token(self) -> None:
        if not self._oauth_manager or not self._refresh_token:
            return

        try:
            token_info = self._oauth_manager.refresh_access_token(self._refresh_token)
        except (spotipy.SpotifyException, requests.RequestException):
            return

        self._access_token = token_info.get("access_token", self._access_token)
        self._refresh_token = token_info.get("refresh_token", self._refresh_token)

    def _get_client(self) -> spotipy.Spotify | None:
        if self._oauth_manager and self._refresh_token:
            self._refresh_access_token()

        if not self._access_token:
            return None

        return spotipy.Spotify(auth=self._access_token)
