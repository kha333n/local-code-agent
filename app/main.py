from __future__ import annotations

import uvicorn
from fastapi import FastAPI

from app.api.routes import router
from app.config import settings
from app.utils.logger import logger

app = FastAPI(title="local-cursor-agent", version="0.1.0")
app.include_router(router)


def run() -> None:
    logger.info("Starting agent server host=%s port=%s", settings.host, settings.port)
    uvicorn.run("app.main:app", host=settings.host, port=settings.port, reload=False)
