from __future__ import annotations

from contextlib import asynccontextmanager
import logging

from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles
import uvicorn

from app.dependencies import ASSETS_DIR
from app.routes import router


logger = logging.getLogger("server_widget_painel")

@asynccontextmanager
async def lifespan(app: FastAPI):
    logger.info("LED Panel Backend iniciado com sucesso")
    print("[server-widget-painel] API ativa em http://0.0.0.0:8000")
    print("[server-widget-painel] Endpoints uteis: /health, /screen, /docs, /endpoints")
    yield


app = FastAPI(
    title="LED Panel Backend",
    version="1.0.0",
    description="Backend FastAPI para painel LED 64x32 com ESP32.",
    lifespan=lifespan,
)

if ASSETS_DIR.exists():
    app.mount("/assets", StaticFiles(directory=str(ASSETS_DIR)), name="assets")

app.include_router(router)


if __name__ == "__main__":
    uvicorn.run(
        "app.main:app",
        host="0.0.0.0",
        port=8000,
        reload=False,
        log_level="info",
        access_log=True,
    )
