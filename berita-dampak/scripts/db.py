"""Koneksi MySQL bersama untuk seluruh pipeline berita-dampak.

Semua tabel memakai prefix "berita_" (konvensi yang sudah dipakai
dashboard_berita_dampak.py dan generate_narasi_llm.py). Kredensial MySQL
dibaca dari .env di root project (MYSQL_HOST/PORT/USER/PASSWORD/DB).

Menggantikan data/ugm_news.duckdb -- seluruh script pipeline sekarang baca/
tulis langsung ke MySQL, tidak ada lagi file DuckDB perantara.

Didesain untuk proses panjang (fetch_detail.py bisa jalan multi-jam, ribuan
request): koneksi di-reconnect otomatis kalau idle/putus (pool_pre_ping +
pool_recycle), semua operasi baca/tulis dibungkus retry (3x, log & lanjut
kalau tetap gagal -- satu item gagal TIDAK menghentikan seluruh pipeline),
dan penulisan baris per-item pakai upsert batch kecil (bukan satu transaksi
raksasa) supaya data yang sudah masuk tidak hilang kalau proses berhenti
di tengah jalan.
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

# Beberapa script print() karakter non-ASCII (≥, →, ×, …). Konsol Windows
# default ke cp1252 (bukan UTF-8) dan akan crash (UnicodeEncodeError) di
# print() itu -- exit code != 0 bikin update_mingguan.py mengira step itu
# GAGAL padahal data sudah tersimpan duluan. Paksa stdout/stderr UTF-8 di
# sini supaya semua script yang `import db` otomatis aman.
for _stream in (sys.stdout, sys.stderr):
    try:
        _stream.reconfigure(encoding="utf-8", errors="replace")
    except Exception:  # noqa: BLE001
        pass

ROOT = Path(__file__).resolve().parents[1]
load_dotenv(ROOT.parent / ".env")

PREFIX = "berita_"
REQUIRED_ENV = ("MYSQL_HOST", "MYSQL_USER", "MYSQL_PASSWORD", "MYSQL_DB")

RETRY_ATTEMPTS = 3
RETRY_DELAY_SEC = 5
UPSERT_CHUNK = 100

logger = logging.getLogger("berita_dampak.db")
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
    # pool_pre_ping: tes koneksi sebelum dipakai, auto-reconnect kalau putus.
    # pool_recycle: buang koneksi setelah 1 jam idle (hindari "MySQL server has
    # gone away" pada proses panjang seperti fetch_detail.py yang bisa jalan
    # berjam-jam).
    return create_engine(url, pool_pre_ping=True, pool_recycle=3600)


def t(name: str) -> str:
    """Nama tabel MySQL dengan prefix 'berita_' (mis. t('sitemap') -> 'berita_sitemap')."""
    return f"{PREFIX}{name}"


def with_retry(
    func: Callable,
    *,
    label: str,
    attempts: int = RETRY_ATTEMPTS,
    delay: float = RETRY_DELAY_SEC,
):
    """Jalankan `func()`; retry sampai `attempts` kali kalau melempar exception
    (jeda `delay` detik antar percobaan). TIDAK melempar ulang exception kalau
    semua percobaan gagal -- supaya caller (loop panjang) bisa log & lanjut ke
    item berikutnya daripada menghentikan seluruh pipeline.

    Return (True, hasil_func) kalau sukses, (False, None) kalau gagal total.
    """
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


def column_exists(engine: Engine, table: str, column: str) -> bool:
    """True kalau `column` ada di `table`. Dipakai script tagging (mis.
    tag_kepmen_all.py) supaya bisa jalan aman baik sebelum maupun sesudah
    scripts/fetch_backlog.py pernah dijalankan (kolom `isi`/`kredit` cuma
    ada setelah itu) -- fallback ke judul+deskripsi kalau kolom belum ada,
    bukan error "Unknown column"."""
    def _check() -> bool:
        with engine.connect() as conn:
            row = conn.exec_driver_sql(
                "SELECT COUNT(*) FROM information_schema.columns "
                "WHERE table_schema = DATABASE() AND table_name = %s AND column_name = %s",
                (table, column),
            ).scalar()
            return bool(row)

    ok, result = with_retry(_check, label=f"cek kolom {table}.{column}")
    return bool(ok and result)


def ensure_url_primary_key(engine: Engine, table: str, varchar_len: int = 500) -> None:
    """Pastikan tabel `table` (kolom `url`) punya PRIMARY KEY.

    Tabel-tabel dasar (berita_sitemap, berita_berita) awalnya dibuat lewat
    pandas to_sql (migrasi awal DuckDB->MySQL) sehingga kolom url bertipe
    TEXT tanpa PRIMARY KEY -- upsert (ON DUPLICATE KEY UPDATE) butuh itu
    untuk tahu baris mana yang "duplikat". Fungsi ini sekali jalan mengubah
    url jadi VARCHAR({varchar_len}) lalu menambahkan PRIMARY KEY; aman
    dipanggil berkali-kali (no-op kalau PK sudah ada). URL ugm.ac.id di data
    saat ini <200 karakter, jauh di bawah batas index InnoDB (768 karakter
    utf8mb4).
    """

    def _check_and_fix() -> None:
        with engine.begin() as conn:
            has_pk = conn.execute(
                text(
                    "SELECT COUNT(*) FROM information_schema.table_constraints "
                    "WHERE table_schema = DATABASE() AND table_name = :tbl "
                    "AND constraint_type = 'PRIMARY KEY'"
                ),
                {"tbl": table},
            ).scalar()
            if has_pk:
                return
            conn.execute(text(
                f"ALTER TABLE `{table}` MODIFY COLUMN `url` VARCHAR({varchar_len}) NOT NULL"
            ))
            conn.execute(text(f"ALTER TABLE `{table}` ADD PRIMARY KEY (`url`)"))

    ok, _ = with_retry(_check_and_fix, label=f"ensure_url_primary_key({table})")
    if not ok:
        raise RuntimeError(f"Gagal memastikan PRIMARY KEY pada `{table}` -- cek koneksi MySQL.")


def upsert(
    engine: Engine,
    table: str,
    columns: list[str],
    rows: list[tuple],
    update_columns: list[str] | None = None,
    chunk_size: int = UPSERT_CHUNK,
    label: str | None = None,
) -> int:
    """INSERT ... ON DUPLICATE KEY UPDATE, dikirim per-batch kecil (default
    100 baris/transaksi) -- bukan satu transaksi raksasa untuk seluruh data.
    Kalau proses berhenti di tengah (atau satu batch gagal terus setelah
    retry), batch yang SUDAH commit tetap tersimpan; batch yang gagal
    di-log dan dilewati (aman dicoba lagi di run berikutnya karena upsert
    idempoten).

    `update_columns` default = semua kolom selain kolom pertama (diasumsikan
    primary key, mis. url). Return jumlah baris yang berhasil tersimpan.
    """
    if not rows:
        return 0
    pk_col = columns[0]
    update_columns = update_columns or [c for c in columns if c != pk_col]
    label = label or f"upsert {table}"

    cols_sql = ", ".join(f"`{c}`" for c in columns)
    placeholders = ", ".join(f":{c}" for c in columns)
    if update_columns:
        # Sintaks alias (MySQL 8.0.19+) -- pengganti VALUES() yang deprecated.
        set_sql = ", ".join(f"`{c}` = new.`{c}`" for c in update_columns)
        sql = text(
            f"INSERT INTO `{table}` ({cols_sql}) VALUES ({placeholders}) AS new "
            f"ON DUPLICATE KEY UPDATE {set_sql}"
        )
    else:
        # Tidak ada kolom lain selain PK -- duplikat cukup diabaikan.
        sql = text(f"INSERT IGNORE INTO `{table}` ({cols_sql}) VALUES ({placeholders})")

    saved = 0
    for i in range(0, len(rows), chunk_size):
        chunk = rows[i : i + chunk_size]
        data = [dict(zip(columns, row)) for row in chunk]

        def _run() -> None:
            with engine.begin() as conn:
                conn.execute(sql, data)

        ok, _ = with_retry(_run, label=f"{label} (baris {i}-{i + len(chunk)})")
        if ok:
            saved += len(chunk)
    return saved


def read_sql_retry(engine: Engine, sql: str, label: str | None = None):
    """pandas.read_sql dibungkus retry (untuk baca awal yang besar sebelum
    loop panjang dimulai)."""
    import pandas as pd

    label = label or f"read_sql: {sql[:60]}"
    ok, df = with_retry(lambda: pd.read_sql(sql, engine), label=label)
    if not ok:
        raise RuntimeError(f"Gagal membaca data dari MySQL ({label}) -- cek koneksi.")
    return df
