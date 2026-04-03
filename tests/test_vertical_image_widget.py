from __future__ import annotations

import base64
import io
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

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

    async def test_save_image_creates_library_with_multiple_assets(self) -> None:
        state_a = self.widget.save_image(
            filename="a.png",
            content_type="image/png",
            raw_bytes=make_png_bytes(width=32, height=96, color=(255, 80, 20)),
            active=True,
        )
        state_b = self.widget.save_image(
            filename="b.png",
            content_type="image/png",
            raw_bytes=make_png_bytes(width=48, height=64, color=(20, 180, 220)),
            active=True,
        )

        self.assertEqual(len(state_a["assets"]), 1)
        self.assertEqual(len(state_b["assets"]), 2)
        self.assertEqual(state_b["active_count"], 2)
        self.assertTrue(state_b["configured"])
        self.assertEqual(state_b["scroll_speed_pps"], 14)
        self.assertEqual(state_b["scroll_direction"], "up")

    async def test_get_data_rotates_between_active_assets(self) -> None:
        self.widget.save_image(
            filename="a.png",
            content_type="image/png",
            raw_bytes=make_png_bytes(width=64, height=120, color=(40, 180, 220)),
            active=True,
        )
        state = self.widget.save_image(
            filename="b.png",
            content_type="image/png",
            raw_bytes=make_png_bytes(width=64, height=140, color=(90, 60, 180)),
            active=True,
        )
        self.widget.update_config(scroll_speed_pps=120)

        assets = state["assets"]
        self.assertEqual(len(assets), 2)

        with patch("app.widgets.vertical_image_widget.time.time", return_value=0.10):
            payload_a = await self.widget.get_data(image_mode="rgb565_base64")
        with patch("app.widgets.vertical_image_widget.time.time", return_value=1.10):
            payload_b = await self.widget.get_data(image_mode="rgb565_base64")

        self.assertIsNotNone(payload_a)
        self.assertIsNotNone(payload_b)
        self.assertEqual(payload_a["widget"], "custom_gif")
        self.assertEqual(payload_b["widget"], "custom_gif")
        self.assertNotEqual(payload_a["data"]["asset_id"], payload_b["data"]["asset_id"])
        self.assertLess(payload_a["data"]["asset_elapsed_ms"], payload_a["data"]["asset_duration_ms"])
        self.assertLess(payload_b["data"]["asset_elapsed_ms"], payload_b["data"]["asset_duration_ms"])

        frame = payload_a["data"]["frame"]
        self.assertEqual(frame["enc"], "rgb565_base64")
        self.assertEqual(frame["w"], 64)
        self.assertEqual(frame["h"], 32)

        decoded = base64.b64decode(frame["data"])
        self.assertEqual(len(decoded), 64 * 32 * 2)

    async def test_asset_reaches_end_before_switching_to_next(self) -> None:
        state = self.widget.save_image(
            filename="a.png",
            content_type="image/png",
            raw_bytes=make_png_bytes(width=64, height=120, color=(255, 40, 40)),
            active=True,
        )
        state = self.widget.save_image(
            filename="b.png",
            content_type="image/png",
            raw_bytes=make_png_bytes(width=64, height=140, color=(40, 255, 40)),
            active=True,
        )
        self.widget.update_config(scroll_speed_pps=120)

        first_asset_id = state["assets"][0]["id"]
        first_scroll_range = int(state["assets"][0]["height"]) - self.widget.frame_height

        with patch("app.widgets.vertical_image_widget.time.time", return_value=0.10):
            start_payload = await self.widget.get_data()
        with patch("app.widgets.vertical_image_widget.time.time", return_value=0.95):
            end_payload = await self.widget.get_data()
        with patch("app.widgets.vertical_image_widget.time.time", return_value=1.10):
            next_payload = await self.widget.get_data()

        self.assertEqual(start_payload["data"]["asset_id"], first_asset_id)
        self.assertEqual(end_payload["data"]["asset_id"], first_asset_id)
        self.assertEqual(end_payload["data"]["scroll_progress_px"], first_scroll_range)
        self.assertNotEqual(next_payload["data"]["asset_id"], first_asset_id)

    async def test_update_asset_active_and_fallback_behavior(self) -> None:
        state = self.widget.save_image(
            filename="a.png",
            content_type="image/png",
            raw_bytes=make_png_bytes(width=64, height=100, color=(100, 10, 10)),
            active=True,
        )
        state = self.widget.save_image(
            filename="b.png",
            content_type="image/png",
            raw_bytes=make_png_bytes(width=64, height=100, color=(0, 220, 0)),
            active=True,
        )
        self.widget.update_config(scroll_speed_pps=120)

        first_id = state["assets"][0]["id"]
        second_id = state["assets"][1]["id"]

        self.widget.update_asset(first_id, active=False)
        with patch("app.widgets.vertical_image_widget.time.time", return_value=1.0):
            payload = await self.widget.get_data()
        self.assertIsNotNone(payload)
        self.assertEqual(payload["data"]["asset_id"], second_id)

        self.widget.update_asset(second_id, active=False)
        with patch("app.widgets.vertical_image_widget.time.time", return_value=1.0):
            none_payload = await self.widget.get_data()
        self.assertIsNone(none_payload)

    async def test_delete_asset_and_clear_image(self) -> None:
        state = self.widget.save_image(
            filename="a.png",
            content_type="image/png",
            raw_bytes=make_png_bytes(width=64, height=80, color=(120, 120, 120)),
            active=True,
        )
        state = self.widget.save_image(
            filename="b.png",
            content_type="image/png",
            raw_bytes=make_png_bytes(width=64, height=80, color=(220, 120, 20)),
            active=True,
        )

        first_id = state["assets"][0]["id"]
        second_id = state["assets"][1]["id"]

        after_delete = self.widget.delete_asset(first_id)
        self.assertEqual(len(after_delete["assets"]), 1)
        self.assertEqual(after_delete["assets"][0]["id"], second_id)

        cleared = self.widget.clear_image()
        self.assertEqual(cleared["assets"], [])
        self.assertFalse(cleared["configured"])
        self.assertIsNone(self.widget.raw_file_path())


if __name__ == "__main__":
    unittest.main()
