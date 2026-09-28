"""Draf suntingan pratinjau Laporan Dampak, disimpan per akun Dampak + per filter laporan.

Suntingan disimpan beserta teks asli paragrafnya: `{indeks: {"asli": ..., "baru": ...}}`. Kalau data
berita berubah dan paragraf di indeks itu tidak lagi sama dengan `asli`, UI tidak memakai suntingan
itu (paragraf baru tidak tertimpa teks lama). SQL portabel; isi disimpan sebagai teks JSON.
"""
from __future__ import annotations

import hashlib
import json
from datetime import datetime
from typing import Any

from sqlalchemy import text
from sqlalchemy.engine import Engine

from app.services import sqlcompat

MAKS_PARAGRAF = 400
MAKS_TEKS = 20_000


class DrafError(ValueError):
    """Isi draf tidak valid (400)."""


def ensure_schema(engine: Engine) -> None:
    teks_panjang = "LONGTEXT" if engine.dialect.name == "mysql" else "TEXT"
    with engine.begin() as conn:
        conn.execute(text(f"""
            CREATE TABLE IF NOT EXISTS laporan_dampak_draf (
                user_id INTEGER NOT NULL,
                kunci CHAR(64) NOT NULL,
                suntingan {teks_panjang} NOT NULL,
                updated_at TIMESTAMP NOT NULL
            )
        """))
    try:
        with engine.begin() as conn:
            conn.execute(text(sqlcompat.index_ddl(engine, "laporan_dampak_draf", ["user_id", "kunci"],
                                                  name="laporan_dampak_draf_kunci", unique=True)))
    except Exception as exc:  # noqa: BLE001 -- index sudah ada
        if not sqlcompat.is_duplicate_index_error(exc):
            raise


def kunci(filter_laporan: dict[str, Any]) -> str:
    """Satu draf per kombinasi mode + filter (urutan kunci tidak berpengaruh)."""
    return hashlib.sha256(json.dumps(filter_laporan, sort_keys=True, ensure_ascii=False, default=str).encode()).hexdigest()


def _bersihkan(suntingan: Any) -> dict[str, dict[str, str]]:
    if not isinstance(suntingan, dict) or len(suntingan) > MAKS_PARAGRAF:
        raise DrafError("Format suntingan tidak valid.")
    bersih: dict[str, dict[str, str]] = {}
    for indeks, isi in suntingan.items():
        if not str(indeks).isdigit() or not isinstance(isi, dict):
            raise DrafError("Format suntingan tidak valid.")
        asli, baru = isi.get("asli"), isi.get("baru")
        if not isinstance(asli, str) or not isinstance(baru, str) or len(baru) > MAKS_TEKS or len(asli) > MAKS_TEKS:
            raise DrafError("Teks suntingan terlalu panjang atau tidak valid.")
        if asli != baru:
            bersih[str(int(indeks))] = {"asli": asli, "baru": baru}
    return bersih


def ambil(engine: Engine, user_id: int, filter_laporan: dict[str, Any]) -> dict[str, Any]:
    with engine.connect() as conn:
        row = conn.execute(text("SELECT suntingan, updated_at FROM laporan_dampak_draf WHERE user_id = :u AND kunci = :k"),
                           {"u": user_id, "k": kunci(filter_laporan)}).first()
    if not row:
        return {"suntingan": {}, "updated_at": None}
    waktu = row[1]
    return {"suntingan": json.loads(row[0]),
            "updated_at": waktu.isoformat(timespec="seconds") if hasattr(waktu, "isoformat") else str(waktu)}


def simpan(engine: Engine, user_id: int, filter_laporan: dict[str, Any], suntingan: Any) -> dict[str, Any]:
    bersih = _bersihkan(suntingan)
    k, now = kunci(filter_laporan), datetime.now()
    with engine.begin() as conn:
        conn.execute(text("DELETE FROM laporan_dampak_draf WHERE user_id = :u AND kunci = :k"), {"u": user_id, "k": k})
        if bersih:
            conn.execute(text("""
                INSERT INTO laporan_dampak_draf (user_id, kunci, suntingan, updated_at) VALUES (:u, :k, :s, :t)
            """), {"u": user_id, "k": k, "s": json.dumps(bersih, ensure_ascii=False), "t": now})
    return {"jumlah": len(bersih), "updated_at": now.isoformat(timespec="seconds")}
