"""Jalankan API FastAPI (api/) terhadap MySQL lokal -- HANYA untuk pratinjau di laptop.

API di api/ dibuat untuk PostgreSQL (lihat api/app/db.py), sedangkan data dashboard
Streamlit ada di MySQL (.env di root repo: MYSQL_HOST/PORT/USER/PASSWORD/DB). Skrip ini
mengganti engine-nya ke MySQL tanpa mengubah kode api/, supaya web React baru bisa
dilihat dengan data yang sama dengan Streamlit.

Batasan: query analitik (Dampak, Dampak x SDGs, SDGs, berita, laporan Word) dan login
akreditasi memakai SQL standar; REGISTRASI akun baru dan UPLOAD file akreditasi memakai
`RETURNING` (khusus Postgres) sehingga tidak jalan di MySQL. Buat akun lewat Streamlit.

Jangan dipakai di server/produksi.
"""
from __future__ import annotations

import os
import sys
from pathlib import Path

from dotenv import load_dotenv
from sqlalchemy import URL, create_engine

ROOT = Path(__file__).resolve().parents[1]
load_dotenv(ROOT / ".env")
sys.path.insert(0, str(ROOT / "api"))

REQUIRED = ("MYSQL_HOST", "MYSQL_USER", "MYSQL_PASSWORD", "MYSQL_DB")
missing = [name for name in REQUIRED if not os.environ.get(name)]
if missing:
    raise SystemExit(f"Variabel .env belum lengkap: {', '.join(missing)}")

import app.db as db  # noqa: E402  (harus diimpor sebelum app.main agar patch berlaku)

_engine = None


def get_mysql_engine():
    global _engine
    if _engine is None:
        url = URL.create(
            "mysql+pymysql",
            username=os.environ["MYSQL_USER"],
            password=os.environ["MYSQL_PASSWORD"],
            host=os.environ["MYSQL_HOST"],
            port=int(os.environ.get("MYSQL_PORT", "3306")),
            database=os.environ["MYSQL_DB"],
            query={"charset": "utf8mb4"},
        )
        _engine = create_engine(url, pool_pre_ping=True, pool_recycle=3600)
    return _engine


db.get_engine = get_mysql_engine

import uvicorn  # noqa: E402
from app.main import app  # noqa: E402

if __name__ == "__main__":
    uvicorn.run(app, host="127.0.0.1", port=int(os.environ.get("API_PORT", "8000")))
