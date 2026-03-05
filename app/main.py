from __future__ import annotations

import uvicorn
from fastapi import FastAPI

from app.api.routes import router
from app.config import settings

app = FastAPI(title="local-cursor-agent", version="0.1.0")
app.include_router(router)


def run() -> None:
    uvicorn.run("app.main:app", host=settings.host, port=settings.port, reload=False)