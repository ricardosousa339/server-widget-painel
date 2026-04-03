from dataclasses import dataclass
from PIL import Image

@dataclass(slots=True)
class GifPlaybackCache:
    mtime: float
    frames: list[Image.Image]
    durations_ms: list[int]
    total_duration_ms: int
