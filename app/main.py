from __future__ import annotations

from contextlib import asynccontextmanager
import logging
from typing import Any

from fastapi import FastAPI, Query
from fastapi.responses import HTMLResponse
from pydantic import BaseModel
import uvicorn

from app.config import get_settings
from app.services.image_service import ImageMode, ImageProcessor
from app.services.widget_manager import WidgetManager
from app.widgets.book_widget import BookWidget
from app.widgets.clock_widget import ClockWidget
from app.widgets.spotify_widget import SpotifyWidget


logger = logging.getLogger("server_widget_painel")


class BookStateUpdate(BaseModel):
    is_reading: bool | None = None
    title: str | None = None
    author: str | None = None
    cover_url: str | None = None

    def to_payload(self) -> dict[str, Any]:
        return {key: value for key, value in self.model_dump().items() if value is not None}


settings = get_settings()
image_processor = ImageProcessor(
    size=settings.image_size,
    timeout_seconds=settings.request_timeout_seconds,
)
spotify_widget = SpotifyWidget(settings=settings, image_processor=image_processor, priority=100)
book_widget = BookWidget(
    image_processor=image_processor,
    state_path=settings.book_state_path,
    priority=50,
)
clock_widget = ClockWidget(priority=0)
widget_manager = WidgetManager(
    primary_widgets=[spotify_widget, book_widget],
    fallback_widget=clock_widget,
)

@asynccontextmanager
async def lifespan(app: FastAPI):
    logger.info("LED Panel Backend iniciado com sucesso")
    print("[server-widget-painel] API ativa em http://0.0.0.0:8000")
    print("[server-widget-painel] Endpoints úteis: /health, /screen, /docs")
    yield


app = FastAPI(
    title="LED Panel Backend",
    version="1.0.0",
    description="Backend FastAPI para painel LED 64x32 com ESP32.",
    lifespan=lifespan,
)


@app.get("/health")
def health() -> dict[str, str]:
    return {"status": "ok"}


@app.get("/")
def root() -> dict[str, Any]:
    return {
        "status": "running",
        "service": "LED Panel Backend",
        "version": app.version,
        "docs": "/docs",
        "health": "/health",
        "screen": "/screen",
    "preview": "/preview/painel",
    }


@app.get("/preview/painel", response_class=HTMLResponse)
def preview_painel() -> HTMLResponse:
        html = """
<!doctype html>
<html lang="pt-BR">
<head>
    <meta charset="utf-8" />
    <meta name="viewport" content="width=device-width,initial-scale=1" />
    <title>Preview Painel LED 64x32</title>
    <style>
        :root {
            --bg: #101217;
            --panel: #1a1e27;
            --frame: #2a2f3b;
            --frame-hi: #3a4152;
            --text: #d7dde8;
            --accent: #4ad7ff;
        }

        * { box-sizing: border-box; }

        body {
            margin: 0;
            min-height: 100vh;
            display: grid;
            place-items: center;
            background: radial-gradient(1200px 600px at 30% 10%, #1a2435, var(--bg));
            color: var(--text);
            font-family: Inter, Segoe UI, Roboto, Arial, sans-serif;
            padding: 24px;
        }

        .layout {
            width: min(1100px, 100%);
            display: grid;
            gap: 18px;
            grid-template-columns: 1fr 280px;
            padding: 10px;
            border-radius: 16px;
            border: 1px solid rgba(255,255,255,.1);
            box-shadow: 0 0 0 1px rgba(255,255,255,.06);
        }

        .bezel {
            background: linear-gradient(145deg, var(--frame-hi), var(--frame));
            border-radius: 22px;
            padding: 22px;
            box-shadow:
                inset 0 0 0 1px #4b5468,
                inset 0 12px 24px rgba(255,255,255,.06),
                0 20px 40px rgba(0,0,0,.5);
            position: relative;
        }

        .screw {
            position: absolute;
            width: 16px;
            height: 16px;
            border-radius: 50%;
            background: radial-gradient(circle at 30% 30%, #adb8ca, #596176 70%);
            box-shadow: inset 0 1px 3px rgba(0,0,0,.5);
        }

        .screw::before {
            content: "";
            position: absolute;
            inset: 7px 2px;
            background: rgba(0,0,0,.45);
            border-radius: 2px;
            transform: rotate(-22deg);
        }

        .s1 { top: 10px; left: 10px; }
        .s2 { top: 10px; right: 10px; }
        .s3 { bottom: 10px; left: 10px; }
        .s4 { bottom: 10px; right: 10px; }

        .panel {
            border-radius: 12px;
            background: #080b10;
            border: 2px solid #0f131a;
            box-shadow:
                inset 0 0 0 1px rgba(255,255,255,.03),
                inset 0 -20px 40px rgba(0,0,0,.35);
            position: relative;
            overflow: hidden;
            aspect-ratio: 2 / 1;
        }

        .led-wrap {
            position: absolute;
            inset: 0;
            display: grid;
            place-items: center;
            padding: 10px;
        }

        canvas#led {
            width: 100%;
            height: 100%;
            image-rendering: pixelated;
            background: #000;
            border-radius: 6px;
        }

        .led-mask {
            position: absolute;
            inset: 10px;
            border-radius: 6px;
            pointer-events: none;
            background-image: radial-gradient(circle at 50% 50%, rgba(255,255,255,.13) 0 18%, rgba(0,0,0,.55) 52%, rgba(0,0,0,.9) 100%);
            background-size: calc(100% / 64) calc(100% / 32);
            mix-blend-mode: soft-light;
            opacity: .8;
        }

        .hud {
            background: linear-gradient(180deg, #171d28, #11151e);
            border: 1px solid #2a3240;
            border-radius: 14px;
            padding: 14px;
            display: grid;
            gap: 12px;
            align-content: start;
        }

        .title { font-size: 14px; color: #9eb2cb; margin: 0; }
        .value { font-size: 13px; line-height: 1.4; word-break: break-word; }
        .pill {
            display: inline-block;
            padding: 6px 10px;
            border-radius: 999px;
            background: rgba(74,215,255,.12);
            color: var(--accent);
            border: 1px solid rgba(74,215,255,.35);
            font-size: 12px;
            font-weight: 600;
        }

        .toolbar {
            display: flex;
            gap: 8px;
            flex-wrap: wrap;
        }

        button, select {
            background: #1a2230;
            color: #d7dde8;
            border: 1px solid #2d3b52;
            border-radius: 8px;
            padding: 8px 10px;
            font-size: 12px;
            cursor: pointer;
        }

        @media (max-width: 960px) {
            .layout { grid-template-columns: 1fr; }
        }
    </style>
</head>
<body>
    <div class="layout">
        <div class="bezel">
            <span class="screw s1"></span><span class="screw s2"></span>
            <span class="screw s3"></span><span class="screw s4"></span>
            <div class="panel">
                <div class="led-wrap">
                    <canvas id="led" width="64" height="32"></canvas>
                </div>
                <div class="led-mask"></div>
            </div>
        </div>

        <aside class="hud">
            <div>
                <p class="title">Widget atual</p>
                <span id="widgetName" class="pill">-</span>
            </div>
            <div>
                <p class="title">Status</p>
                <div id="status" class="value">Carregando...</div>
            </div>
            <div>
                <p class="title">Detalhes</p>
                <div id="details" class="value">-</div>
            </div>
            <div class="toolbar">
                <button id="refreshNow">Atualizar agora</button>
                <select id="refreshMs">
                    <option value="1000">1s</option>
                    <option value="2000" selected>2s</option>
                    <option value="5000">5s</option>
                </select>
                <select id="borderMode" title="Intensidade do contorno">
                    <option value="off">Borda LEDs: Off</option>
                    <option value="subtle">Borda LEDs: Sutil</option>
                    <option value="strong" selected>Borda LEDs: Forte</option>
                </select>
            </div>
        </aside>
    </div>

    <script>
        const canvas = document.getElementById('led');
        const ctx = canvas.getContext('2d', { alpha: false });
        const detailsEl = document.getElementById('details');
        const statusEl = document.getElementById('status');
        const widgetEl = document.getElementById('widgetName');
        const refreshMsEl = document.getElementById('refreshMs');
        const refreshNowEl = document.getElementById('refreshNow');
        const borderModeEl = document.getElementById('borderMode');

        let timer = null;

        function clearCanvas() {
            ctx.fillStyle = '#000';
            ctx.fillRect(0, 0, 64, 32);
        }

        function fitText(text, maxLen) {
            return (text || '').length > maxLen ? `${text.slice(0, maxLen - 1)}…` : (text || '');
        }

        function marqueeText(text, maxLen, tickMs = 380) {
            const source = String(text || '');
            if (source.length <= maxLen) return source;
            const padded = `${source}   `;
            const start = Math.floor(Date.now() / tickMs) % padded.length;
            const looped = padded + padded;
            return looped.slice(start, start + maxLen);
        }

        function drawMonoText(text, x, y, opts = {}) {
            const {
                color = '#f5f7ff',
                font = '7px monospace',
            } = opts;

            ctx.font = font;
            ctx.fillStyle = color;
            ctx.fillText(text, x, y);
        }

        function drawClock(data) {
            clearCanvas();
            ctx.fillStyle = '#000';
            ctx.fillRect(0, 0, 64, 32);

            drawMonoText(data.time || '--:--', 2, 14, { font: 'bold 14px monospace' });
            drawMonoText(`${data.seconds || '00'}s`, 49, 14);
            drawMonoText((data.weekday || '---').toUpperCase(), 2, 25);
            drawMonoText(data.date || '--/--', 34, 25);
        }

        function decodeRgb565ToImageData(base64, w, h) {
            const bin = atob(base64);
            const imageData = ctx.createImageData(w, h);
            let p = 0;
            for (let i = 0; i < bin.length; i += 2) {
                const value = (bin.charCodeAt(i) << 8) | bin.charCodeAt(i + 1);
                const r = ((value >> 11) & 0x1F) * 255 / 31;
                const g = ((value >> 5) & 0x3F) * 255 / 63;
                const b = (value & 0x1F) * 255 / 31;
                imageData.data[p++] = r;
                imageData.data[p++] = g;
                imageData.data[p++] = b;
                imageData.data[p++] = 255;
            }
            return imageData;
        }

        function getDominantColorFromImageData(imageData) {
            const data = imageData.data;
            let r = 0;
            let g = 0;
            let b = 0;
            let count = 0;

            for (let i = 0; i < data.length; i += 4) {
                const pr = data[i];
                const pg = data[i + 1];
                const pb = data[i + 2];
                const luminance = 0.2126 * pr + 0.7152 * pg + 0.0722 * pb;

                if (luminance < 12 || luminance > 245) {
                    continue;
                }

                r += pr;
                g += pg;
                b += pb;
                count += 1;
            }

            if (count === 0) {
                return null;
            }

            return {
                r: Math.round(r / count),
                g: Math.round(g / count),
                b: Math.round(b / count),
            };
        }

        function drawLedOuterBorder(rgb) {
            const mode = borderModeEl?.value || 'strong';
            if (mode === 'off' || !rgb) {
                return;
            }

            const alpha = mode === 'strong' ? 1 : 0.72;
            const lineColor = `rgba(${rgb.r}, ${rgb.g}, ${rgb.b}, ${alpha})`;

            ctx.fillStyle = lineColor;
            // linha superior e inferior
            ctx.fillRect(0, 0, 64, 1);
            ctx.fillRect(0, 31, 64, 1);
            // linha esquerda e direita
            ctx.fillRect(0, 0, 1, 32);
            ctx.fillRect(63, 0, 1, 32);
        }

        function drawCover(cover) {
            if (!cover || !cover.data || cover.enc !== 'rgb565_base64') return null;
            const w = cover.w || 32;
            const h = cover.h || 32;
            const imageData = decodeRgb565ToImageData(cover.data, w, h);
            const off = document.createElement('canvas');
            off.width = w;
            off.height = h;
            const offCtx = off.getContext('2d');
            offCtx.putImageData(imageData, 0, 0);
            ctx.drawImage(off, 0, 0, 32, 32);

            const dominant = getDominantColorFromImageData(imageData);
            return dominant;
        }

        function drawMediaLike(data, label) {
            clearCanvas();
            const dominant = drawCover(data.cover);

            ctx.fillStyle = 'rgba(0,0,0,.78)';
            ctx.fillRect(32, 0, 32, 32);

            drawMonoText(label.toUpperCase(), 33, 7);

            // Em 64x32 priorizamos apenas o essencial para legibilidade.
            const title = marqueeText(data.track || data.title || '-', 12, 280);
            const author = marqueeText(data.artist || data.author || '-', 12, 380);

            drawMonoText(title, 33, 16, { font: 'bold 8px monospace' });
            drawMonoText(author, 33, 26);

            if (label === 'spotify' && data.duration_ms > 0) {
                const progressRatio = Math.max(0, Math.min(1, (data.progress_ms || 0) / data.duration_ms));
                ctx.fillStyle = 'rgba(255,255,255,.2)';
                ctx.fillRect(1, 30, 30, 1);
                ctx.fillStyle = '#37e283';
                ctx.fillRect(1, 30, Math.floor(30 * progressRatio), 1);
            }

            drawLedOuterBorder(dominant);
        }

        async function render() {
            try {
                const res = await fetch('/screen?img_mode=rgb565_base64', { cache: 'no-store' });
                const payload = await res.json();
                const widget = payload.widget || 'none';
                const data = payload.data || {};

                widgetEl.textContent = widget;
                statusEl.textContent = `Atualizado em ${new Date().toLocaleTimeString()}`;
                detailsEl.textContent = JSON.stringify(data, null, 2).slice(0, 300);

                if (widget === 'clock') {
                    drawClock(data);
                } else if (widget === 'spotify') {
                    drawMediaLike(data, 'spotify');
                } else if (widget === 'book') {
                    drawMediaLike(data, 'book');
                } else {
                    clearCanvas();
                    ctx.fillStyle = '#ff7f7f';
                    ctx.font = '7px monospace';
                    ctx.fillText('sem widget ativo', 6, 18);
                }
            } catch (err) {
                widgetEl.textContent = 'erro';
                statusEl.textContent = 'Falha ao buscar /screen';
                detailsEl.textContent = String(err);
            }
        }

        function startTimer() {
            if (timer) clearInterval(timer);
            const interval = Number(refreshMsEl.value || 2000);
            timer = setInterval(render, interval);
        }

        refreshMsEl.addEventListener('change', startTimer);
        refreshNowEl.addEventListener('click', render);
        borderModeEl.addEventListener('change', render);

        render();
        startTimer();
    </script>
</body>
</html>
        """
        return HTMLResponse(content=html)


@app.get("/screen")
async def screen(
    img_mode: ImageMode = Query(
        default="rgb565_base64",
        description="Formato da imagem para ESP32: rgb565_base64, rgb_base64, rgb_array",
    ),
) -> dict[str, Any]:
    return await widget_manager.get_screen_payload(image_mode=img_mode)


@app.get("/book/current")
def get_current_book() -> dict[str, Any]:
    return book_widget.get_state()


@app.post("/book/current")
def update_current_book(update: BookStateUpdate) -> dict[str, Any]:
    payload = update.to_payload()
    return book_widget.update_state(payload)


if __name__ == "__main__":
    uvicorn.run(
        "app.main:app",
        host="0.0.0.0",
        port=8000,
        reload=False,
        log_level="info",
        access_log=True,
    )
