from __future__ import annotations

import base64
import math
import time
from pathlib import Path
from typing import Any

from PIL import Image, ImageDraw, ImageFont


class FrameRenderer:
    def __init__(
        self,
        width: int = 64,
        height: int = 32,
        font_path: Path | None = None,
        border_mode: str = "strong",
    ) -> None:
        self.width = width
        self.height = height
        self.font_path = Path(font_path) if font_path is not None else None
        self.border_mode = border_mode

        self._font_cache: dict[int, ImageFont.FreeTypeFont | ImageFont.ImageFont] = {}
        self._marquee_state_by_key: dict[str, dict[str, int | str]] = {}

    def render_payload(self, payload: dict[str, Any], now_ms: int | None = None) -> dict[str, Any]:
        render_now_ms = now_ms if now_ms is not None else int(time.time() * 1000)

        frame = Image.new("RGB", (self.width, self.height), (0, 0, 0))
        widget = str(payload.get("widget", "none"))
        data = payload.get("data") or {}

        if widget == "clock":
            self._draw_clock(frame, data)
        elif widget in {"spotify", "book"}:
            self._draw_media_like(frame, data, label=widget, now_ms=render_now_ms)
        else:
            self._draw_fallback(frame)

        return {
            "widget": widget,
            "priority": int(payload.get("priority", -1)),
            "ts": int(time.time()),
            "frame": self._encode_frame_payload(frame),
        }

    def _draw_fallback(self, frame: Image.Image) -> None:
        self._draw_binary_text(
            frame,
            "sem widget ativo",
            x=6,
            baseline_y=18,
            font_size=8,
            clip_x=0,
            clip_width=self.width,
            threshold=96,
            letter_spacing=0,
        )
        self._force_monochrome(frame, threshold=96)

    def _draw_clock(self, frame: Image.Image, data: dict[str, Any]) -> None:
        clock_text = str(data.get("time") or "--:--")
        weekday = str(data.get("weekday") or "---").upper()
        date = str(data.get("date") or "--/--")

        # Replica o preview LED: linha principal em baseline alphabetic com y=2+ascent.
        # Em Pillow, getmetrics() superestima ascent para esta fonte; usamos bbox na baseline.
        main_font = self._get_font(16)
        main_ascent, _main_descent = self._text_baseline_metrics(clock_text, main_font)
        main_clock_y = 2 + main_ascent

        self._draw_mono_text(
            frame,
            clock_text,
            x=3,
            baseline_y=main_clock_y,
            font_size=16,
            clip_width=self.width,
            baseline="alphabetic",
        )

        self._draw_mono_text(
            frame,
            weekday,
            x=3,
            baseline_y=30,
            font_size=8,
            clip_width=32,
            baseline="alphabetic",
        )
        self._draw_mono_text(
            frame,
            date,
            x=34,
            baseline_y=30,
            font_size=8,
            clip_width=32,
            baseline="alphabetic",
        )

        self._force_monochrome(frame, threshold=96)

    def _draw_media_like(self, frame: Image.Image, data: dict[str, Any], label: str, now_ms: int) -> None:
        cover_width = 26
        text_x = cover_width + 1
        text_width = self.width - text_x
        title_x = text_x + 1
        title_width = max(1, self.width - title_x)
        author_x = text_x + 1
        author_width = max(1, self.width - author_x)

        dominant = self._draw_cover(frame, data.get("cover"), target_size=cover_width)

        draw = ImageDraw.Draw(frame)
        draw.rectangle(
            (cover_width, 0, self.width - 1, self.height - 1),
            fill=(0, 0, 0),
        )

        title_source = str(data.get("track") or data.get("title") or "-")
        title_text, title_offset = self._marquee_text_by_pixels(
            title_source,
            max_width_px=title_width,
            font_size=8,
            now_ms=now_ms,
            tick_ms=280,
            gap_chars=3,
            end_blackout_ticks=2,
            letter_spacing=1,
            step_px=1,
            state_key=f"{label}:title",
        )

        raw_author = str(data.get("artist") or data.get("author") or "-")
        author_source = raw_author
        if label == "spotify" and data.get("artist"):
            author_source = self._compact_artist_name(raw_author)

        author_text, author_offset = self._marquee_text_by_pixels(
            author_source,
            max_width_px=author_width,
            font_size=8,
            now_ms=now_ms,
            tick_ms=380,
            gap_chars=3,
            end_blackout_ticks=0,
            letter_spacing=1,
            step_px=1,
            state_key=f"{label}:author",
        )

        self._draw_binary_text(
            frame,
            title_text,
            x=title_x - title_offset,
            baseline_y=14,
            font_size=8,
            clip_x=title_x,
            clip_width=title_width,
            threshold=96,
            letter_spacing=1,
        )

        self._draw_binary_text(
            frame,
            author_text,
            x=author_x - author_offset,
            baseline_y=26,
            font_size=8,
            clip_x=author_x,
            clip_width=author_width,
            threshold=96,
            letter_spacing=1,
        )

        duration_ms = int(data.get("duration_ms") or 0)
        progress_ms = int(data.get("progress_ms") or 0)
        if label == "spotify" and duration_ms > 0:
            progress_ratio = max(0.0, min(1.0, progress_ms / duration_ms))
            progress_track_width = max(1, text_width - 2)
            progress_px = int(math.floor(progress_track_width * progress_ratio))

            draw.rectangle(
                (text_x, 29, text_x + progress_track_width - 1, 29),
                fill=(52, 52, 52),
            )
            if progress_px > 0:
                draw.rectangle(
                    (text_x, 29, text_x + progress_px - 1, 29),
                    fill=(55, 226, 131),
                )

        self._draw_led_outer_border(frame, dominant)

    def _draw_cover(self, frame: Image.Image, cover: Any, target_size: int = 24) -> dict[str, int] | None:
        if not isinstance(cover, dict):
            return None

        if str(cover.get("enc") or "") != "rgb565_base64":
            return None

        try:
            width = int(cover.get("w") or 32)
            height = int(cover.get("h") or 32)
        except (TypeError, ValueError):
            return None

        if width <= 0 or height <= 0:
            return None

        encoded = str(cover.get("data") or "")
        if not encoded:
            return None

        try:
            image = self._decode_rgb565_to_image(encoded, width, height)
        except ValueError:
            return None

        src_ratio = width / height
        dst_ratio = 1.0
        sx = 0
        sy = 0
        sw = width
        sh = height

        if src_ratio > dst_ratio:
            sw = round(height * dst_ratio)
            sx = (width - sw) // 2
        elif src_ratio < dst_ratio:
            sh = round(width / dst_ratio)
            sy = (height - sh) // 2

        cropped = image.crop((sx, sy, sx + sw, sy + sh))
        resampling = getattr(Image, "Resampling", Image)
        resized = cropped.resize((target_size, target_size), resampling.NEAREST)

        dst_x = 0
        dst_y = (self.height - target_size) // 2
        frame.paste(resized, (dst_x, dst_y))

        return self._get_dominant_color(image)

    def _decode_rgb565_to_image(self, encoded: str, width: int, height: int) -> Image.Image:
        try:
            raw = base64.b64decode(encoded, validate=True)
        except (base64.binascii.Error, ValueError) as exc:
            raise ValueError("invalid base64 rgb565 payload") from exc

        expected = width * height * 2
        if len(raw) != expected:
            raise ValueError("unexpected rgb565 payload size")

        pixels: list[tuple[int, int, int]] = []
        for index in range(0, len(raw), 2):
            value = (raw[index] << 8) | raw[index + 1]
            red = int(((value >> 11) & 0x1F) * 255 / 31)
            green = int(((value >> 5) & 0x3F) * 255 / 63)
            blue = int((value & 0x1F) * 255 / 31)
            pixels.append((red, green, blue))

        image = Image.new("RGB", (width, height))
        image.putdata(pixels)
        return image

    def _get_dominant_color(self, image: Image.Image) -> dict[str, int] | None:
        rgb = image.convert("RGB")
        data = rgb.tobytes()

        red_sum = 0
        green_sum = 0
        blue_sum = 0
        count = 0

        for index in range(0, len(data), 3):
            red = data[index]
            green = data[index + 1]
            blue = data[index + 2]
            luminance = 0.2126 * red + 0.7152 * green + 0.0722 * blue

            if luminance < 12 or luminance > 245:
                continue

            red_sum += red
            green_sum += green
            blue_sum += blue
            count += 1

        if count == 0:
            return None

        return {
            "r": round(red_sum / count),
            "g": round(green_sum / count),
            "b": round(blue_sum / count),
        }

    def _draw_led_outer_border(self, frame: Image.Image, rgb: dict[str, int] | None) -> None:
        if self.border_mode == "off" or rgb is None:
            return

        alpha = 1.0 if self.border_mode == "strong" else 0.72

        pixels = frame.load()
        overlay = (
            int(rgb["r"]),
            int(rgb["g"]),
            int(rgb["b"]),
        )

        for x in range(self.width):
            top = pixels[x, 0]
            bottom = pixels[x, self.height - 1]
            pixels[x, 0] = self._blend_rgb(top, overlay, alpha)
            pixels[x, self.height - 1] = self._blend_rgb(bottom, overlay, alpha)

    def _blend_rgb(self, base: tuple[int, int, int], overlay: tuple[int, int, int], alpha: float) -> tuple[int, int, int]:
        inv = 1.0 - alpha
        return (
            int(round(base[0] * inv + overlay[0] * alpha)),
            int(round(base[1] * inv + overlay[1] * alpha)),
            int(round(base[2] * inv + overlay[2] * alpha)),
        )

    def _compact_artist_name(self, artist: str) -> str:
        normalized = " ".join(str(artist or "").split())
        if not normalized:
            return "-"

        words = normalized.split(" ")
        if len(words) < 2:
            return words[0]

        second_initial = words[1][:1]
        if not second_initial:
            return words[0]

        return f"{words[0]} {second_initial}."

    def _marquee_text_by_pixels(
        self,
        text: str,
        max_width_px: int,
        font_size: int,
        now_ms: int,
        tick_ms: int,
        gap_chars: int = 3,
        end_blackout_ticks: int = 0,
        letter_spacing: int = 0,
        step_px: int = 1,
        state_key: str | None = None,
    ) -> tuple[str, int]:
        source = str(text or "-")
        if not source:
            return "-", 0

        font = self._get_font(font_size)
        text_width_px = self._measure_text_width(source, font, letter_spacing)
        if text_width_px <= max_width_px:
            return source, 0

        safe_gap_chars = max(0, int(gap_chars))
        padded = source + (" " * safe_gap_chars)
        gap_width_px = self._measure_text_width(" " * safe_gap_chars, font, letter_spacing)
        travel_px = max(1, int(math.ceil(text_width_px + gap_width_px)))

        safe_step_px = max(1, int(step_px))
        blackout_px = max(0, int(end_blackout_ticks)) * safe_step_px
        cycle_px = travel_px + blackout_px

        safe_tick_ms = max(1, int(tick_ms))
        effective_key = state_key or f"marquee:{font_size}:{max_width_px}:{source}"
        state = self._marquee_state_by_key.get(effective_key)

        if state is None or state.get("source") != source:
            self._marquee_state_by_key[effective_key] = {
                "source": source,
                "started_at": now_ms,
            }
            state = self._marquee_state_by_key[effective_key]

        started_at = int(state.get("started_at", now_ms))
        tick_index = (now_ms - started_at) // safe_tick_ms
        phase_px = int((tick_index * safe_step_px) % cycle_px)

        if phase_px >= travel_px:
            return "", 0

        return padded, phase_px

    def _measure_text_width(self, text: str, font: ImageFont.FreeTypeFont | ImageFont.ImageFont, letter_spacing: int = 0) -> float:
        source = str(text or "")
        if not source:
            return 0.0

        if letter_spacing > 0:
            width = 0.0
            for char in source:
                width += self._raw_text_width(char, font)
            width += max(0, len(source) - 1) * letter_spacing
            return width

        return self._raw_text_width(source, font)

    def _raw_text_width(self, text: str, font: ImageFont.FreeTypeFont | ImageFont.ImageFont) -> float:
        if not text:
            return 0.0

        if hasattr(font, "getlength"):
            return float(font.getlength(text))

        bbox = font.getbbox(text)
        return float(max(0, bbox[2] - bbox[0]))

    def _draw_binary_text(
        self,
        frame: Image.Image,
        text: str,
        x: float,
        baseline_y: float,
        font_size: int,
        clip_width: int | None = None,
        clip_x: int | None = None,
        threshold: int = 96,
        letter_spacing: int = 0,
    ) -> None:
        source = str(text or "")
        if not source:
            return

        font = self._get_font(font_size)
        mask, ascent = self._render_text_mask(
            source,
            font=font,
            threshold=threshold,
            letter_spacing=letter_spacing,
        )

        dst_x = int(math.floor(x))
        dst_y = int(math.floor(baseline_y - ascent - 1))

        if clip_width is None:
            frame.paste((255, 255, 255), (dst_x, dst_y), mask)
            return

        clip_left = int(math.floor(clip_x if clip_x is not None else x))
        clip_right = clip_left + int(max(0, clip_width))

        src_left = max(0, clip_left - dst_x)
        src_right = min(mask.width, clip_right - dst_x)
        if src_right <= src_left:
            return

        clipped_mask = mask.crop((src_left, 0, src_right, mask.height))
        paste_x = max(dst_x, clip_left)
        frame.paste((255, 255, 255), (paste_x, dst_y), clipped_mask)

    def _draw_mono_text(
        self,
        frame: Image.Image,
        text: str,
        x: float,
        baseline_y: float,
        font_size: int,
        clip_width: int | None = None,
        baseline: str = "alphabetic",
    ) -> None:
        source = str(text or "")
        if not source:
            return

        font = self._get_font(font_size)

        bx = int(math.floor(x))
        by = int(math.floor(baseline_y))

        mask = Image.new("L", (self.width, self.height), 0)
        draw = ImageDraw.Draw(mask)
        if baseline == "alphabetic":
            draw.text((bx, by), source, fill=255, font=font, anchor="ls")
        else:
            draw.text((bx, by), source, fill=255, font=font, anchor="lt")

        if clip_width is not None:
            clip_left = max(0, bx)
            clip_right = min(self.width, bx + int(max(0, clip_width)))
            if clip_right <= clip_left:
                return

            clipped = Image.new("L", (self.width, self.height), 0)
            region = mask.crop((clip_left, 0, clip_right, self.height))
            clipped.paste(region, (clip_left, 0))
            mask = clipped

        frame.paste((255, 255, 255), (0, 0), mask)

    def _text_baseline_metrics(
        self,
        text: str,
        font: ImageFont.FreeTypeFont | ImageFont.ImageFont,
    ) -> tuple[int, int]:
        source = str(text or "")
        if not source:
            return self._font_metrics(font)

        try:
            _left, top, _right, bottom = font.getbbox(source, anchor="ls")
        except TypeError:
            probe = Image.new("L", (1, 1), 0)
            draw = ImageDraw.Draw(probe)
            _left, top, _right, bottom = draw.textbbox((0, 0), source, font=font, anchor="ls")

        ascent = max(0, int(-top))
        descent = max(0, int(bottom))
        return ascent, descent

    def _render_text_mask(
        self,
        text: str,
        font: ImageFont.FreeTypeFont | ImageFont.ImageFont,
        threshold: int,
        letter_spacing: int = 0,
    ) -> tuple[Image.Image, int]:
        ascent, descent = self._font_metrics(font)
        measured_width = int(math.ceil(self._measure_text_width(text, font, letter_spacing)))
        render_width = max(1, measured_width)
        render_height = max(1, ascent + descent + 2)

        mask = Image.new("L", (render_width, render_height), 0)
        draw = ImageDraw.Draw(mask)

        if letter_spacing > 0:
            cursor_x = 0.0
            for char in text:
                if cursor_x > render_width:
                    break
                draw.text((cursor_x, 1), char, fill=255, font=font)
                cursor_x += self._raw_text_width(char, font) + letter_spacing
        else:
            draw.text((0, 1), text, fill=255, font=font)

        safe_threshold = max(0, min(255, int(threshold)))
        binary = mask.point(lambda value: 255 if value >= safe_threshold else 0)
        return binary, ascent

    def _font_metrics(self, font: ImageFont.FreeTypeFont | ImageFont.ImageFont) -> tuple[int, int]:
        if hasattr(font, "getmetrics"):
            ascent, descent = font.getmetrics()
            return int(ascent), int(abs(descent))

        bbox = font.getbbox("Hg")
        height = max(1, bbox[3] - bbox[1])
        ascent = max(1, int(height * 0.75))
        descent = max(1, height - ascent)
        return ascent, descent

    def _force_monochrome(self, image: Image.Image, threshold: int = 96) -> None:
        self._force_monochrome_region(
            image,
            x=0,
            y=0,
            width=self.width,
            height=self.height,
            threshold=threshold,
        )

    def _force_monochrome_region(
        self,
        image: Image.Image,
        x: int,
        y: int,
        width: int,
        height: int,
        threshold: int,
    ) -> None:
        x0 = max(0, int(math.floor(x)))
        y0 = max(0, int(math.floor(y)))
        w = min(self.width - x0, int(math.ceil(width)))
        h = min(self.height - y0, int(math.ceil(height)))
        if w <= 0 or h <= 0:
            return

        safe_threshold = max(0, min(255, int(threshold)))
        pixels = image.load()

        for py in range(y0, y0 + h):
            for px in range(x0, x0 + w):
                red, green, blue = pixels[px, py]
                luminance = 0.2126 * red + 0.7152 * green + 0.0722 * blue
                value = 255 if luminance >= safe_threshold else 0
                pixels[px, py] = (value, value, value)

    def _encode_frame_payload(self, frame: Image.Image) -> dict[str, Any]:
        rgb565_bytes = self._to_rgb565_bytes(frame)
        encoded = base64.b64encode(rgb565_bytes).decode("ascii")
        return {
            "w": self.width,
            "h": self.height,
            "enc": "rgb565_base64",
            "data": encoded,
        }

    def _to_rgb565_bytes(self, image: Image.Image) -> bytes:
        rgb = image.convert("RGB")
        rgb_bytes = rgb.tobytes()
        rgb565 = bytearray()

        for index in range(0, len(rgb_bytes), 3):
            red = rgb_bytes[index]
            green = rgb_bytes[index + 1]
            blue = rgb_bytes[index + 2]

            value = ((red & 0xF8) << 8) | ((green & 0xFC) << 3) | (blue >> 3)
            rgb565.append((value >> 8) & 0xFF)
            rgb565.append(value & 0xFF)

        return bytes(rgb565)

    def _get_font(self, font_size: int) -> ImageFont.FreeTypeFont | ImageFont.ImageFont:
        cached = self._font_cache.get(font_size)
        if cached is not None:
            return cached

        if self.font_path is not None and self.font_path.exists():
            font = ImageFont.truetype(str(self.font_path), size=font_size)
        else:
            font = ImageFont.load_default()

        self._font_cache[font_size] = font
        return font
