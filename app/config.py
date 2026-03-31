from dataclasses import dataclass
import os
from pathlib import Path

from dotenv import load_dotenv


load_dotenv()


def _as_bool(value: str, default: bool = False) -> bool:
    normalized = value.strip().lower()
    if normalized in {"1", "true", "yes", "on"}:
        return True
    if normalized in {"0", "false", "no", "off"}:
        return False
    return default


def _as_csv_tuple(value: str) -> tuple[str, ...]:
    parts = [part.strip() for part in value.split(",") if part.strip()]
    return tuple(parts)


@dataclass(frozen=True)
class Settings:
    image_size: int = int(os.getenv("IMAGE_SIZE", "32"))
    request_timeout_seconds: float = float(os.getenv("REQUEST_TIMEOUT_SECONDS", "6"))

    spotify_client_id: str = os.getenv("SPOTIPY_CLIENT_ID", "")
    spotify_client_secret: str = os.getenv("SPOTIPY_CLIENT_SECRET", "")
    spotify_redirect_uri: str = os.getenv(
        "SPOTIPY_REDIRECT_URI", "http://localhost:8888/callback"
    )
    spotify_refresh_token: str = os.getenv("SPOTIFY_REFRESH_TOKEN", "")
    spotify_access_token: str = os.getenv("SPOTIFY_ACCESS_TOKEN", "")

    book_state_path: Path = Path(os.getenv("BOOK_STATE_PATH", "data/current_book.json"))

    skoob_sync_enabled: bool = _as_bool(os.getenv("SKOOB_SYNC_ENABLED", "false"))
    skoob_sync_interval_seconds: int = int(
        os.getenv("SKOOB_SYNC_INTERVAL_SECONDS", "300")
    )
    skoob_profile_url: str = os.getenv("SKOOB_PROFILE_URL", "")
    skoob_user_id: str = os.getenv("SKOOB_USER_ID", "")
    skoob_auth_cookie: str = os.getenv("SKOOB_AUTH_COOKIE", "")
    skoob_reading_types: tuple[str, ...] = _as_csv_tuple(
        os.getenv("SKOOB_READING_TYPES", "2")
    )


def get_settings() -> Settings:
    return Settings()
