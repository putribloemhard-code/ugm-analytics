"""Koneksi MySQL bersama untuk subproyek akreditasi.

Semua tabel memakai prefix "akreditasi_" (paralel konvensi "berita_" di
berita-dampak/scripts/db.py -- pola direplikasi dari sana, bukan di-*import*
lintas subproyek, supaya akreditasi/ berdiri sendiri). Database MySQL SAMA
dengan berita-dampak (`ugm_analytics`, kredensial .env di root project),
cuma beda prefix tabel.

Didesain sama seperti berita-dampak/scripts/db.py: koneksi di-reconnect
otomatis kalau idle/putus (pool_pre_ping + pool_recycle), operasi baca/tulis
dibungkus retry.
"""

import logging
import os
import sys
import time
from pathlib import Path
from typing import Callable

from dotenv import load_dotenv
from sqlalchemy import create_engine, text
from sqlalchemy.engine import Engine

# Konsol Windows default cp1252 -- paksa UTF-8 supaya print() karakter
# non-ASCII (emoji status, dsb.) tidak crash script yang `import db`.
for _stream in (sys.stdout, sys.stderr):
    try:
        _stream.reconfigure(encoding="utf-8", errors="replace")
    except Exception:  # noqa: BLE001
        pass

ROOT = Path(__file__).resolve().parents[1]
load_dotenv(ROOT.parent / ".env")

PREFIX = "akreditasi_"
REQUIRED_ENV = ("MYSQL_HOST", "MYSQL_USER", "MYSQL_PASSWORD", "MYSQL_DB")

RETRY_ATTEMPTS = 3
RETRY_DELAY_SEC = 5

logger = logging.getLogger("akreditasi.db")
if not logger.handlers:
    _h = logging.StreamHandler()
    _h.setFormatter(logging.Formatter("%(asctime)s [%(levelname)s] %(message)s"))
    logger.addHandler(_h)
    logger.setLevel(logging.INFO)


def get_engine() -> Engine:
    missing = [k for k in REQUIRED_ENV if not os.environ.get(k)]
    if missing:
        raise RuntimeError(
            f"Env MySQL belum lengkap ({', '.join(missing)}) -- isi .env di root project "
            f"(MYSQL_HOST, MYSQL_PORT, MYSQL_USER, MYSQL_PASSWORD, MYSQL_DB)."
        )
    host = os.environ["MYSQL_HOST"]
    port = os.environ.get("MYSQL_PORT", "3306")
    user = os.environ["MYSQL_USER"]
    password = os.environ["MYSQL_PASSWORD"]
    db = os.environ["MYSQL_DB"]
    url = f"mysql+pymysql://{user}:{password}@{host}:{port}/{db}"
    return create_engine(url, pool_pre_ping=True, pool_recycle=3600)


def t(name: str) -> str:
    """Nama tabel MySQL dengan prefix 'akreditasi_' (mis. t('data_manual') -> 'akreditasi_data_manual')."""
    return f"{PREFIX}{name}"


def with_retry(
    func: Callable,
    *,
    label: str,
    attempts: int = RETRY_ATTEMPTS,
    delay: float = RETRY_DELAY_SEC,
):
    """Jalankan `func()`; retry sampai `attempts` kali kalau melempar exception.
    Return (True, hasil_func) kalau sukses, (False, None) kalau gagal total
    (di-log, TIDAK melempar ulang exception)."""
    last_err: Exception | None = None
    for attempt in range(1, attempts + 1):
        try:
            return True, func()
        except Exception as e:  # noqa: BLE001
            last_err = e
            if attempt < attempts:
                logger.warning(f"[RETRY {attempt}/{attempts}] {label} gagal: {e}")
                time.sleep(delay)
    logger.error(f"[GAGAL] {label} gagal setelah {attempts} percobaan: {last_err}")
    return False, None


def table_exists(engine: Engine, table: str) -> bool:
    def _check() -> bool:
        with engine.connect() as conn:
            row = conn.exec_driver_sql(
                "SELECT COUNT(*) FROM information_schema.tables "
                "WHERE table_schema = DATABASE() AND table_name = %s",
                (table,),
            ).scalar()
            return bool(row)

    ok, result = with_retry(_check, label=f"cek tabel {table}")
    return bool(ok and result)


def read_sql_retry(engine: Engine, sql: str, label: str | None = None, params: dict | None = None):
    """pandas.read_sql dibungkus retry."""
    import pandas as pd

    label = label or f"read_sql: {sql[:60]}"
    ok, df = with_retry(lambda: pd.read_sql(text(sql), engine, params=params), label=label)
    if not ok:
        raise RuntimeError(f"Gagal membaca data dari MySQL ({label}) -- cek koneksi.")
    return df
