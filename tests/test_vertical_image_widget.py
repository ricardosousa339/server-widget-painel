from __future__ import annotations

import base64
import io
import tempfile
import unittest
from pathlib import Path

from PIL import Image

from app.widgets.vertical_image_widget import VerticalImageWidget


def make_png_bytes(*, width: int, height: int, color: tuple[int, int, int]) -> bytes:
    image = Image.new("RGB", (width, height), color)
    output = io.BytesIO()
    image.save(output, format="PNG")
    return output.getvalue()


class VerticalImageWidgetTests(unittest.IsolatedAsyncioTestCase):
    def setUp(self) -> None:
        self.tmpdir = tempfile.TemporaryDirectory()
        base_path = Path(self.tmpdir.name)
        self.state_path = base_path / "vertical_image_state.json"
        self.upload_dir = base_path / "uploads"
        self.widget = VerticalImageWidget(
            state_path=self.state_path,
            upload_dir=self.upload_dir,
            frame_width=64,
            frame_height=32,
            max_upload_bytes=1024 * 1024,
            default_scroll_speed_pps=14,
        )

    def tearDown(self) -> None:
        self.tmpdir.cleanup()

    async def test_save_image_normalizes_width_and_exposes_state(self) -> None:
        raw = make_png_bytes(width=32, height=96, color=(255, 80, 20))

        state = self.widget.save_image(
            filename="poster.png",
            content_type="image/png",
            raw_bytes=raw,
            active=True,
        )

        asset = state["asset"]
        self.assertIsNotNone(asset)
        self.assertEqual(asset["width"], 64)
        self.assertEqual(asset["height"], 192)
        self.assertTrue(asset["available"])
        self.assertTrue(state["configured"])
        self.assertEqual(state["scroll_speed_pps"], 14)

    async def test_get_data_returns_rgb565_frame_payload_when_active(self) -> None:
        raw = make_png_bytes(width=64, height=120, color=(40, 180, 220))
        self.widget.save_image(
            filename="long.png",
            content_type="image/png",
            raw_bytes=raw,
            active=True,
        )

        payload = await self.widget.get_data(image_mode="rgb565_base64")

        self.assertIsNotNone(payload)
        self.assertEqual(payload["widget"], "vertical_image")
        frame = payload["data"]["frame"]
        self.assertEqual(frame["enc"], "rgb565_base64")
        self.assertEqual(frame["w"], 64)
        self.assertEqual(frame["h"], 32)

        decoded = base64.b64decode(frame["data"])
        self.assertEqual(len(decoded), 64 * 32 * 2)
        self.assertGreaterEqual(payload["data"]["scroll_progress_px"], 0)
        self.assertGreaterEqual(payload["data"]["scroll_range_px"], 0)

    async def test_get_data_returns_none_when_asset_inactive(self) -> None:
        raw = make_png_bytes(width=64, height=80, color=(100, 10, 10))
        self.widget.save_image(
            filename="inactive.png",
            content_type="image/png",
            raw_bytes=raw,
            active=False,
        )

        payload = await self.widget.get_data()
        self.assertIsNone(payload)

    async def test_clear_image_removes_asset(self) -> None:
        raw = make_png_bytes(width=64, height=80, color=(0, 220, 0))
        saved_state = self.widget.save_image(
            filename="remove.png",
            content_type="image/png",
            raw_bytes=raw,
            active=True,
        )
        self.assertIsNotNone(saved_state["asset"])

        cleared = self.widget.clear_image()
        self.assertIsNone(cleared["asset"])
        self.assertFalse(cleared["configured"])
        self.assertIsNone(self.widget.raw_file_path())


if __name__ == "__main__":
    unittest.main()
