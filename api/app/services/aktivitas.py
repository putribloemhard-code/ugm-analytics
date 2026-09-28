"""Log aktivitas dua portal: siapa melakukan apa, kapan.

Dipakai untuk dua tampilan:
- "Riwayat perubahan" per laporan akreditasi (isian butir, final, unggah, ekstraksi, unduh Word),
  karena satu laporan dikerjakan beberapa staf prodi.
- "Aktivitas terbaru" di halaman Admin kedua portal (aksi admin, PIN prodi, tautan reset, dll.).

Dicatat di lapisan endpoint SETELAH aksinya berhasil. Kegagalan mencatat tidak boleh menggagalkan
aksi pengguna, jadi `catat` menelan galat dan hanya menulis ke log server. SQL portabel.
"""
from __future__ import annotations

import logging
from datetime import datetime
from typing import Any

from sqlalchemy import text
from sqlalchemy.engine import Engine

from app.services import sqlcompat

logger = logging.getLogger(__name__)
PORTAL = {"akreditasi", "dampak"}
MAKS_DAFTAR = 200


def ensure_schema(engine: Engine) -> None:
    id_clause = {
        "postgresql": "SERIAL PRIMARY KEY",
        "mysql": "INTEGER NOT NULL AUTO_INCREMENT PRIMARY KEY",
        "sqlite": "INTEGER NOT NULL PRIMARY KEY AUTOINCREMENT",
    }.get(engine.dialect.name, "INTEGER NOT NULL PRIMARY KEY")
    with engine.begin() as conn:
        conn.execute(text(f"""
            CREATE TABLE IF NOT EXISTS aktivitas_log (
                id {id_clause},
                portal VARCHAR(16) NOT NULL,
                laporan_id INTEGER,
                pelaku_email VARCHAR(254) NOT NULL,
                pelaku_nama VARCHAR(100),
                aksi VARCHAR(64) NOT NULL,
                keterangan VARCHAR(500) NOT NULL,
                created_at TIMESTAMP NOT NULL
            )
        """))
    for kolom, nama in ((["portal", "created_at"], "aktivitas_log_portal"), (["laporan_id", "created_at"], "aktivitas_log_laporan")):
        try:
            with engine.begin() as conn:
                conn.execute(text(sqlcompat.index_ddl(engine, "aktivitas_log", kolom, name=nama)))
        except Exception as exc:  # noqa: BLE001 -- index sudah ada
            if not sqlcompat.is_duplicate_index_error(exc):
                raise


def catat(engine: Engine, portal: str, pelaku: dict[str, Any], aksi: str, keterangan: str,
          laporan_id: int | None = None) -> None:
    try:
        with engine.begin() as conn:
            conn.execute(text("""
                INSERT INTO aktivitas_log (portal, laporan_id, pelaku_email, pelaku_nama, aksi, keterangan, created_at)
                VALUES (:p, :l, :e, :n, :a, :k, :t)
            """), {"p": portal, "l": laporan_id, "e": str(pelaku.get("email") or "")[:254],
                   "n": (str(pelaku.get("nama") or "")[:100] or None), "a": aksi[:64], "k": keterangan[:500],
                   "t": datetime.now()})
    except Exception:  # noqa: BLE001 -- log aktivitas tidak boleh menggagalkan aksi pengguna
        logger.exception("aktivitas gagal dicatat (%s %s)", portal, aksi)


def _baris(r: Any) -> dict[str, Any]:
    d = dict(r)
    waktu = d.get("created_at")
    d["created_at"] = waktu.isoformat(timespec="minutes") if hasattr(waktu, "isoformat") else str(waktu)
    return d


def daftar(engine: Engine, portal: str, laporan_id: int | None = None, limit: int = 50) -> list[dict[str, Any]]:
    if portal not in PORTAL:
        raise ValueError("Portal tidak dikenal.")
    limit = max(1, min(int(limit), MAKS_DAFTAR))
    syarat, param = "portal = :p", {"p": portal}
    if laporan_id is not None:
        syarat += " AND laporan_id = :l"
        param["l"] = laporan_id
    with engine.connect() as conn:
        rows = conn.execute(text(f"""
            SELECT id, laporan_id, pelaku_email, pelaku_nama, aksi, keterangan, created_at
            FROM aktivitas_log WHERE {syarat} ORDER BY created_at DESC, id DESC LIMIT {limit}
        """), param).mappings().all()
    return [_baris(r) for r in rows]
