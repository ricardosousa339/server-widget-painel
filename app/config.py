from dataclasses import dataclass
import os
from pathlib import Path

from dotenv import load_dotenv


load_dotenv()


@dataclass(frozen=True)
class Settings:
    image_size: int = int(os.getenv("IMAGE_SIZE", "32"))
    request_timeout_seconds: float = float(os.getenv("REQUEST_TIMEOUT_SECONDS", "6"))
    frame_source_refresh_ms: int = int(os.getenv("FRAME_SOURCE_REFRESH_MS", "1500"))

    spotify_client_id: str = os.getenv("SPOTIPY_CLIENT_ID", "")
    spotify_client_secret: str = os.getenv("SPOTIPY_CLIENT_SECRET", "")
    spotify_redirect_uri: str = os.getenv(
        "SPOTIPY_REDIRECT_URI", "http://localhost:8888/callback"
    )
    spotify_refresh_token: str = os.getenv("SPOTIFY_REFRESH_TOKEN", "")
    spotify_access_token: str = os.getenv("SPOTIFY_ACCESS_TOKEN", "")

    widget_config_path: Path = Path(os.getenv("WIDGET_CONFIG_PATH", "data/widget_config.json"))
    custom_gif_state_path: Path = Path(
        os.getenv("CUSTOM_GIF_STATE_PATH", "data/custom_gif_state.json")
    )
    custom_gif_upload_dir: Path = Path(
        os.getenv("CUSTOM_GIF_UPLOAD_DIR", "data/uploads")
    )
    custom_gif_max_upload_bytes: int = int(
        os.getenv("CUSTOM_GIF_MAX_UPLOAD_BYTES", str(8 * 1024 * 1024))
    )


def get_settings() -> Settings:
    return Settings()
