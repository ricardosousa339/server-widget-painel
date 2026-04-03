from __future__ import annotations

import unittest

from app.services.widget_manager import WidgetManager


class FakeWidget:
    def __init__(self, name: str, priority: int, result: object) -> None:
        self.name = name
        self.priority = priority
        self.result = result
        self.calls: list[dict[str, object]] = []

    async def get_data(self, image_mode: str = "rgb565_base64", **kwargs: object):
        self.calls.append({"image_mode": image_mode, **kwargs})
        if callable(self.result):
            return self.result(image_mode=image_mode, **kwargs)
        return self.result


class ExplodingWidget(FakeWidget):
    async def get_data(self, image_mode: str = "rgb565_base64", **kwargs: object):
        self.calls.append({"image_mode": image_mode, **kwargs})
        raise RuntimeError(f"boom:{self.name}")


class FakeConfigStore:
    def __init__(self, state: dict[str, object]) -> None:
        self.state = state

    def get_state(self) -> dict[str, object]:
        return self.state

    def enabled_set(self) -> set[str]:
        enabled_widgets = self.state.get("enabled_widgets")
        if isinstance(enabled_widgets, list):
            return {str(name) for name in enabled_widgets}
        return set()


def make_custom_payload(*, image_mode: str = "rgb565_base64", **kwargs: object) -> dict[str, object]:
    return {
        "widget": "custom_gif",
        "priority": 80,
        "ts": 1234567890,
        "data": {
            "kind": kwargs.get("kind"),
            "asset_id": kwargs.get("asset_id"),
            "playhead_ms": kwargs.get("playhead_ms"),
            "image_mode": image_mode,
        },
    }


class WidgetManagerPriorityTests(unittest.IsolatedAsyncioTestCase):
    async def test_spotify_wins_over_doorbell_and_gif_windows(self) -> None:
        spotify_widget = FakeWidget(
            "spotify",
            100,
            {
                "widget": "spotify",
                "priority": 100,
                "ts": 1234567890,
                "data": {"currently_playing": True, "track": "Song"},
            },
        )
        custom_widget = FakeWidget("custom_gif", 80, make_custom_payload)
        clock_widget = FakeWidget(
            "clock",
            0,
            {
                "widget": "clock",
                "priority": 0,
                "ts": 1234567890,
                "data": {"time": "12:00"},
            },
        )
        manager = WidgetManager(
            primary_widgets=[spotify_widget, custom_widget],
            fallback_widget=clock_widget,
            config_store=FakeConfigStore(
                {
                    "enabled_widgets": ["spotify", "custom_gif", "clock"],
                    "display_mode": "hybrid",
                    "hybrid_period_seconds": 2,
                    "hybrid_show_seconds": 2,
                    "updated_at": 1,
                }
            ),
        )

        manager.trigger_doorbell_alert(duration_seconds=30, source="home_assistant")

        payload = await manager.get_screen_payload()

        self.assertEqual(payload["widget"], "spotify")
        self.assertEqual(spotify_widget.calls, [{"image_mode": "rgb565_base64"}])
        self.assertEqual(custom_widget.calls, [])
        self.assertEqual(clock_widget.calls, [])
        self.assertNotIn("doorbell_alert", payload["data"])

    async def test_doorbell_still_uses_custom_gif_when_spotify_is_inactive(self) -> None:
        spotify_widget = FakeWidget("spotify", 100, None)
        custom_widget = FakeWidget("custom_gif", 80, make_custom_payload)
        clock_widget = FakeWidget(
            "clock",
            0,
            {
                "widget": "clock",
                "priority": 0,
                "ts": 1234567890,
                "data": {"time": "12:00"},
            },
        )
        manager = WidgetManager(
            primary_widgets=[spotify_widget, custom_widget],
            fallback_widget=clock_widget,
            config_store=FakeConfigStore(
                {
                    "enabled_widgets": ["spotify", "custom_gif", "clock"],
                    "display_mode": "priority",
                    "hybrid_period_seconds": 300,
                    "hybrid_show_seconds": 30,
                    "updated_at": 1,
                }
            ),
        )

        manager.trigger_doorbell_alert(duration_seconds=30, source="home_assistant")

        payload = await manager.get_screen_payload()

        self.assertEqual(payload["widget"], "custom_gif")
        self.assertEqual(custom_widget.calls[0]["kind"], "doorbell")
        self.assertEqual(payload["data"]["doorbell_alert"]["active"], True)
        self.assertEqual(payload["data"]["doorbell_alert"]["last_source"], "home_assistant")

    async def test_spotify_grace_avoids_transient_fallback_to_gif(self) -> None:
        responses = [
            {
                "widget": "spotify",
                "priority": 100,
                "ts": 1234567890,
                "data": {
                    "currently_playing": True,
                    "track": "Song",
                    "artist": "Artist",
                    "progress_ms": 1000,
                    "duration_ms": 200000,
                },
            },
            None,
        ]

        def spotify_result(**_kwargs: object):
            if responses:
                return responses.pop(0)
            return None

        spotify_widget = FakeWidget("spotify", 100, spotify_result)
        custom_widget = FakeWidget("custom_gif", 80, make_custom_payload)
        clock_widget = FakeWidget(
            "clock",
            0,
            {
                "widget": "clock",
                "priority": 0,
                "ts": 1234567890,
                "data": {"time": "12:00"},
            },
        )
        manager = WidgetManager(
            primary_widgets=[spotify_widget, custom_widget],
            fallback_widget=clock_widget,
            config_store=FakeConfigStore(
                {
                    "enabled_widgets": ["spotify", "custom_gif", "clock"],
                    "display_mode": "hybrid",
                    "hybrid_period_seconds": 2,
                    "hybrid_show_seconds": 2,
                    "updated_at": 1,
                }
            ),
            spotify_grace_seconds=8,
        )

        manager.trigger_doorbell_alert(duration_seconds=30, source="home_assistant")

        first_payload = await manager.get_screen_payload()
        second_payload = await manager.get_screen_payload()

        self.assertEqual(first_payload["widget"], "spotify")
        self.assertEqual(second_payload["widget"], "spotify")
        self.assertEqual(second_payload["data"]["grace_cached"], True)
        self.assertEqual(len(custom_widget.calls), 0)

    async def test_spotify_grace_can_be_disabled(self) -> None:
        responses = [
            {
                "widget": "spotify",
                "priority": 100,
                "ts": 1234567890,
                "data": {
                    "currently_playing": True,
                    "track": "Song",
                    "artist": "Artist",
                    "progress_ms": 1000,
                    "duration_ms": 200000,
                },
            },
            None,
        ]

        def spotify_result(**_kwargs: object):
            if responses:
                return responses.pop(0)
            return None

        spotify_widget = FakeWidget("spotify", 100, spotify_result)
        custom_widget = FakeWidget("custom_gif", 80, make_custom_payload)
        clock_widget = FakeWidget(
            "clock",
            0,
            {
                "widget": "clock",
                "priority": 0,
                "ts": 1234567890,
                "data": {"time": "12:00"},
            },
        )
        manager = WidgetManager(
            primary_widgets=[spotify_widget, custom_widget],
            fallback_widget=clock_widget,
            config_store=FakeConfigStore(
                {
                    "enabled_widgets": ["spotify", "custom_gif", "clock"],
                    "display_mode": "priority",
                    "hybrid_period_seconds": 300,
                    "hybrid_show_seconds": 30,
                    "updated_at": 1,
                }
            ),
            spotify_grace_seconds=0,
        )

        manager.trigger_doorbell_alert(duration_seconds=30, source="home_assistant")

        first_payload = await manager.get_screen_payload()
        second_payload = await manager.get_screen_payload()

        self.assertEqual(first_payload["widget"], "spotify")
        self.assertEqual(second_payload["widget"], "custom_gif")
        self.assertEqual(custom_widget.calls[0]["kind"], "doorbell")

    async def test_custom_only_falls_back_to_vertical_image_before_clock(self) -> None:
        spotify_widget = FakeWidget("spotify", 100, None)
        custom_widget = FakeWidget("custom_gif", 80, None)
        vertical_widget = FakeWidget(
            "vertical_image",
            70,
            {
                "widget": "vertical_image",
                "priority": 70,
                "ts": 1234567890,
                "data": {
                    "asset_id": "vertical-1",
                    "frame": {
                        "w": 64,
                        "h": 32,
                        "enc": "rgb565_base64",
                        "data": "",
                    },
                },
            },
        )
        clock_widget = FakeWidget(
            "clock",
            0,
            {
                "widget": "clock",
                "priority": 0,
                "ts": 1234567890,
                "data": {"time": "12:00"},
            },
        )
        manager = WidgetManager(
            primary_widgets=[spotify_widget, custom_widget, vertical_widget],
            fallback_widget=clock_widget,
            config_store=FakeConfigStore(
                {
                    "enabled_widgets": ["spotify", "custom_gif", "vertical_image", "clock"],
                    "display_mode": "custom_only",
                    "hybrid_period_seconds": 300,
                    "hybrid_show_seconds": 30,
                    "updated_at": 1,
                }
            ),
        )

        payload = await manager.get_screen_payload()

        self.assertEqual(payload["widget"], "vertical_image")
        self.assertEqual(len(custom_widget.calls), 1)
        self.assertEqual(len(spotify_widget.calls), 2)
        self.assertEqual(len(vertical_widget.calls), 1)
        self.assertEqual(len(clock_widget.calls), 0)

    async def test_primary_widget_exception_does_not_break_payload_selection(self) -> None:
        spotify_widget = ExplodingWidget("spotify", 100, None)
        custom_widget = FakeWidget("custom_gif", 80, make_custom_payload)
        clock_widget = FakeWidget(
            "clock",
            0,
            {
                "widget": "clock",
                "priority": 0,
                "ts": 1234567890,
                "data": {"time": "12:00"},
            },
        )
        manager = WidgetManager(
            primary_widgets=[spotify_widget, custom_widget],
            fallback_widget=clock_widget,
            config_store=FakeConfigStore(
                {
                    "enabled_widgets": ["spotify", "custom_gif", "clock"],
                    "display_mode": "priority",
                    "hybrid_period_seconds": 300,
                    "hybrid_show_seconds": 30,
                    "updated_at": 1,
                }
            ),
        )

        payload = await manager.get_screen_payload()

        self.assertEqual(payload["widget"], "custom_gif")
        self.assertEqual(len(spotify_widget.calls), 2)
        self.assertEqual(len(custom_widget.calls), 1)

    async def test_all_primary_exceptions_fall_back_to_clock(self) -> None:
        spotify_widget = ExplodingWidget("spotify", 100, None)
        custom_widget = ExplodingWidget("custom_gif", 80, None)
        clock_widget = FakeWidget(
            "clock",
            0,
            {
                "widget": "clock",
                "priority": 0,
                "ts": 1234567890,
                "data": {"time": "12:00"},
            },
        )
        manager = WidgetManager(
            primary_widgets=[spotify_widget, custom_widget],
            fallback_widget=clock_widget,
            config_store=FakeConfigStore(
                {
                    "enabled_widgets": ["spotify", "custom_gif", "clock"],
                    "display_mode": "priority",
                    "hybrid_period_seconds": 300,
                    "hybrid_show_seconds": 30,
                    "updated_at": 1,
                }
            ),
        )

        payload = await manager.get_screen_payload()

        self.assertEqual(payload["widget"], "clock")
        self.assertEqual(len(clock_widget.calls), 1)

    async def test_fallback_exception_returns_none_payload(self) -> None:
        spotify_widget = ExplodingWidget("spotify", 100, None)
        custom_widget = ExplodingWidget("custom_gif", 80, None)
        clock_widget = ExplodingWidget("clock", 0, None)
        manager = WidgetManager(
            primary_widgets=[spotify_widget, custom_widget],
            fallback_widget=clock_widget,
            config_store=FakeConfigStore(
                {
                    "enabled_widgets": ["spotify", "custom_gif", "clock"],
                    "display_mode": "priority",
                    "hybrid_period_seconds": 300,
                    "hybrid_show_seconds": 30,
                    "updated_at": 1,
                }
            ),
        )

        payload = await manager.get_screen_payload()

        self.assertEqual(payload["widget"], "none")


if __name__ == "__main__":
    unittest.main()
