from __future__ import annotations

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.api.v1.analytics import router as analytics_router
from app.config import settings

app = FastAPI(title="UGM Analytics API", version="0.1.0")
app.add_middleware(
    CORSMiddleware,
    allow_origins=list(settings.api_cors_origins),
    allow_credentials=False,
    allow_methods=["GET", "POST"],
    allow_headers=["Content-Type"],
)
app.include_router(analytics_router, prefix=settings.api_prefix)


@app.get("/healthz", tags=["system"])
def healthz():
    return {"status": "ok"}
