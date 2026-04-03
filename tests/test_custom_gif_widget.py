from __future__ import annotations

import io
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from PIL import Image

from app.widgets.custom_gif_widget import CustomGifWidget


def make_gif_bytes(frame_colors: list[tuple[int, int, int]], durations_ms: list[int]) -> bytes:
    frames = [Image.new("RGB", (64, 32), color) for color in frame_colors]
    output = io.BytesIO()
    frames[0].save(
        output,
        format="GIF",
        save_all=True,
        append_images=frames[1:],
        duration=durations_ms,
        loop=0,
    )
    return output.getvalue()


class CustomGifWidgetSelectionTests(unittest.IsolatedAsyncioTestCase):
    def setUp(self) -> None:
        self.tmpdir = tempfile.TemporaryDirectory()
        base_path = Path(self.tmpdir.name)
        self.state_path = base_path / "custom_gif_state.json"
        self.upload_dir = base_path / "uploads"
        self.widget = CustomGifWidget(
            state_path=self.state_path,
            upload_dir=self.upload_dir,
            frame_width=64,
            frame_height=32,
        )

    def tearDown(self) -> None:
        self.tmpdir.cleanup()

    async def test_rotates_evenly_across_active_assets(self) -> None:
        long_gif = make_gif_bytes(
            frame_colors=[(220, 40, 40), (200, 30, 30), (180, 20, 20), (160, 10, 10), (140, 0, 0), (120, 0, 0), (100, 0, 0), (80, 0, 0)],
            durations_ms=[1000, 1000, 1000, 1000, 1000, 1000, 1000, 1000],
        )
        short_gif = make_gif_bytes(
            frame_colors=[(40, 120, 220), (30, 110, 200)],
            durations_ms=[100, 100],
        )

        self.widget.save_gif(
            filename="first.gif",
            content_type="image/gif",
            raw_bytes=long_gif,
            active=True,
        )
        second_state = self.widget.save_gif(
            filename="second.gif",
            content_type="image/gif",
            raw_bytes=short_gif,
            active=True,
        )

        first_asset_id = second_state["custom"]["assets"][0]["id"]
        second_asset_id = second_state["custom"]["assets"][1]["id"]

        with patch("app.widgets.custom_gif_widget.time.time", return_value=1.0):
            first_payload = await self.widget.get_data(image_mode="rgb_array")

        with patch("app.widgets.custom_gif_widget.time.time", return_value=6.0):
            second_payload = await self.widget.get_data()

        self.assertIsNotNone(first_payload)
        self.assertIsNotNone(second_payload)
        self.assertEqual(first_payload["data"]["asset_id"], first_asset_id)
        self.assertEqual(first_payload["data"]["selected_index"], 0)
        self.assertEqual(first_payload["data"]["frame"]["enc"], "rgb_array")
        self.assertEqual(len(first_payload["data"]["frame"]["data"]), 64 * 32)
        self.assertEqual(second_payload["data"]["asset_id"], second_asset_id)
        self.assertEqual(second_payload["data"]["selected_index"], 1)

    async def test_skips_missing_active_assets(self) -> None:
        first_gif = make_gif_bytes(
            frame_colors=[(220, 180, 30), (200, 160, 20), (180, 140, 10), (160, 120, 0)],
            durations_ms=[1000, 1000, 1000, 1000],
        )
        second_gif = make_gif_bytes(
            frame_colors=[(20, 180, 220), (10, 160, 200)],
            durations_ms=[100, 100],
        )

        self.widget.save_gif(
            filename="missing.gif",
            content_type="image/gif",
            raw_bytes=first_gif,
            active=True,
        )
        second_state = self.widget.save_gif(
            filename="available.gif",
            content_type="image/gif",
            raw_bytes=second_gif,
            active=True,
        )

        first_asset_id = second_state["custom"]["assets"][0]["id"]
        second_asset_id = second_state["custom"]["assets"][1]["id"]

        missing_path = self.widget.raw_file_path(asset_id=first_asset_id)
        self.assertIsNotNone(missing_path)
        assert missing_path is not None
        missing_path.unlink()

        with patch("app.widgets.custom_gif_widget.time.time", return_value=1.0):
            payload = await self.widget.get_data()

        self.assertIsNotNone(payload)
        self.assertEqual(payload["data"]["asset_id"], second_asset_id)
        self.assertEqual(payload["data"]["selected_index"], 0)


if __name__ == "__main__":
    unittest.main()