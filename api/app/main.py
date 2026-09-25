from __future__ import annotations

from contextlib import asynccontextmanager
from typing import AsyncIterator

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.middleware.gzip import GZipMiddleware
from fastapi.responses import JSONResponse
from sqlalchemy.exc import InterfaceError, OperationalError

from app.api.v1.analytics import router as analytics_router
from app.config import settings


@asynccontextmanager
async def lifespan(_: FastAPI) -> AsyncIterator[None]:
    # Siapkan tabel akun login Analisis Dampak (independen dari akreditasi_users/sessions).
    try:
        from app.db import get_engine
        from app.services.dampak_auth import ensure_schema
        from app.services.sdg_manual import ensure_schema as ensure_sdg_manual
        from app.services.tema_manual import ensure_schema as ensure_tema_manual
        ensure_schema(get_engine())
        ensure_sdg_manual(get_engine())
        ensure_tema_manual(get_engine())
        from app.services.accreditation_laporan import ensure_schema as ensure_laporan
        ensure_laporan(get_engine())
    except Exception:
        # DB belum menyala saat start -- biarkan; endpoint /dampak/auth/* akan tetap gagal
        # dengan 503 seperti biasa (lihat database_unreachable di bawah), bukan meng-crash proses API.
        pass
    yield


app = FastAPI(title="UGM Analytics API", version="0.1.0", lifespan=lifespan)
app.add_middleware(
    CORSMiddleware,
    allow_origins=list(settings.api_cors_origins),
    allow_credentials=False,
    allow_methods=["GET", "POST"],
    allow_headers=["Content-Type"],
)
# /analytics/story bisa >1 MB JSON (bab laporan + mata kuliah); gzip memangkasnya ~80%.
app.add_middleware(GZipMiddleware, minimum_size=1024)
app.include_router(analytics_router, prefix=settings.api_prefix)


@app.exception_handler(OperationalError)
@app.exception_handler(InterfaceError)
async def database_unreachable(request: Request, exc: Exception) -> JSONResponse:
    """DB tidak bisa dihubungi -> 503 dengan pesan yang bisa ditindaklanjuti.

    Tanpa ini klien hanya melihat "500 Internal Server Error" dan mengira kodenya rusak,
    padahal penyebab tersering di laptop adalah servis MySQL yang belum menyala.
    """
    return JSONResponse(
        status_code=503,
        content={
            "detail": (
                "Basis data tidak dapat dihubungi. Pastikan servis database sudah menyala "
                "(di Windows: services.msc -> MySQL80 -> Start), lalu coba lagi."
            ),
            "penyebab": str(getattr(exc, "orig", exc)).splitlines()[0][:300],
        },
    )


@app.get("/healthz", tags=["system"])
def healthz():
    return {"status": "ok"}


@app.get("/healthz/db", tags=["system"])
def healthz_db():
    """Cek cepat: apakah API bisa menyentuh basis data? Berguna sebelum menyalahkan dashboard."""
    from app.db import get_engine
    from sqlalchemy import text

    try:
        with get_engine().connect() as conn:
            conn.execute(text("SELECT 1"))
    except Exception as exc:  # noqa: BLE001 - apa pun penyebabnya, laporkan apa adanya
        return JSONResponse(
            status_code=503,
            content={
                "status": "database-tidak-terhubung",
                "penyebab": str(getattr(exc, "orig", exc)).splitlines()[0][:300],
            },
        )
    return {"status": "ok", "database": "terhubung"}
