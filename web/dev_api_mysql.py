"""Jalankan API FastAPI (api/) terhadap MySQL lokal -- mode kerja lokal di laptop.

API di api/ dibuat untuk PostgreSQL (lihat api/app/db.py), sedangkan data lokal (hasil
pipeline berita-dampak & akreditasi) ada di MySQL (.env di root repo:
MYSQL_HOST/PORT/USER/PASSWORD/DB). Skrip ini mengganti engine-nya ke MySQL tanpa mengubah
kode api/. Dipanggil oleh jalankan_web_baru.bat.

Semua fitur memakai SQL standar dan jalan di MySQL: analitik (Dampak, Dampak x SDGs, SDGs,
berita, laporan Word), login & registrasi (akreditasi + Analisis Dampak), serta ruang kerja
akreditasi (isi data, upload, ekstraksi AI, generate Word).

File unggahan & laporan Word akreditasi disimpan di akreditasi/data/uploads dan
akreditasi/data/generated (folder yang dipakai dashboard Streamlit dulu, jadi file & riwayat
lama tetap bisa dibuka) -- kecuali ACCREDITATION_UPLOAD_DIR / ACCREDITATION_GENERATED_DIR
di-set. Ekstraksi AI aktif kalau OPENAI_API_KEY ada di .env.

Jangan dipakai di server/produksi.
"""
from __future__ import annotations

import os
import sys
from pathlib import Path

# Laptop dengan RAM tipis: OpenBLAS/numpy mengalokasikan buffer per thread dan bisa gagal
# ("Memory allocation still failed") sebelum API sempat menyala. Satu thread cukup untuk pratinjau.
for _var in ("OPENBLAS_NUM_THREADS", "OMP_NUM_THREADS", "MKL_NUM_THREADS"):
    os.environ.setdefault(_var, "1")

from dotenv import load_dotenv
from sqlalchemy import URL, create_engine

ROOT = Path(__file__).resolve().parents[1]
load_dotenv(ROOT / ".env")
os.environ.setdefault("ACCREDITATION_UPLOAD_DIR", str(ROOT / "akreditasi" / "data" / "uploads"))
os.environ.setdefault("ACCREDITATION_GENERATED_DIR", str(ROOT / "akreditasi" / "data" / "generated"))
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
