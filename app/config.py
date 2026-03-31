from dataclasses import dataclass
import os
from pathlib import Path

from dotenv import load_dotenv


load_dotenv()


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


def get_settings() -> Settings:
    return Settings()
