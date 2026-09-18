"""Migrasi akreditasi_data_manual: tambah kolom prodi_id -- WAJIB dijalankan
sebelum ada pengisian data baru lewat form "Simpan" di /akreditasi.

Masalah yang diperbaiki: tabel ini sebelumnya single-tenant (UNIQUE KEY
cuma item_id, baris_ke, kolom, tahun -- TANPA pembeda prodi). Kalau data
prodi lain diisi dengan item_id yang sama (mis. "identitas_pt_upps_ps"),
baris prodi sebelumnya akan TERTIMPA, bukan tersimpan terpisah -- karena
UNIQUE KEY constraint MySQL bikin baris baru meng-update (ON DUPLICATE
KEY) atau bentrok (INSERT biasa) dgn baris lama yg item_id-nya sama,
walau prodi-nya beda.

Perbaikan:
1. Tambah kolom prodi_id VARCHAR(64) NOT NULL DEFAULT 'mei' -- default
   'mei' otomatis mem-backfill baris existing (kalau ada) tanpa langkah
   terpisah, sekaligus jadi default utk INSERT yang belum di-update kodenya.
2. Ganti UNIQUE KEY jadi (prodi_id, item_id, baris_ke, kolom, tahun).

Idempoten -- aman dijalankan berkali-kali (cek dulu kolom/key sudah ada
atau belum sebelum ALTER).

Jalankan:
    ..\\venv\\Scripts\\python.exe scripts\\migrasi_prodi_id.py
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

import db  # noqa: E402

TABLE = db.t("data_manual")
DEFAULT_PRODI = "mei"


def _column_exists(engine, table: str, column: str) -> bool:
    with engine.connect() as conn:
        n = conn.exec_driver_sql(
            "SELECT COUNT(*) FROM information_schema.columns "
            "WHERE table_schema = DATABASE() AND table_name = %s AND column_name = %s",
            (table, column),
        ).scalar()
    return bool(n)


def _key_exists(engine, table: str, key_name: str) -> bool:
    with engine.connect() as conn:
        n = conn.exec_driver_sql(
            "SELECT COUNT(*) FROM information_schema.statistics "
            "WHERE table_schema = DATABASE() AND table_name = %s AND index_name = %s",
            (table, key_name),
        ).scalar()
    return bool(n)


def main() -> None:
    engine = db.get_engine()
    if not db.table_exists(engine, TABLE):
        raise SystemExit(f"Tabel {TABLE} belum ada -- jalankan dulu scripts/migrasi_tabel_akreditasi.py")

    # Langkah 1: tambah kolom prodi_id (kalau belum ada)
    if _column_exists(engine, TABLE, "prodi_id"):
        print(f"SKIP -- kolom prodi_id sudah ada di {TABLE}.")
    else:
        def _add_column():
            with engine.begin() as conn:
                conn.exec_driver_sql(
                    f"ALTER TABLE `{TABLE}` "
                    f"ADD COLUMN `prodi_id` VARCHAR(64) NOT NULL DEFAULT '{DEFAULT_PRODI}' "
                    f"AFTER `id`"
                )
        ok, _ = db.with_retry(_add_column, label="ALTER TABLE ADD COLUMN prodi_id")
        if not ok:
            raise SystemExit("GAGAL menambah kolom prodi_id -- batal.")
        print(f"OK -- kolom prodi_id ditambahkan (DEFAULT '{DEFAULT_PRODI}', otomatis mem-backfill baris existing).")

    # Langkah 1b: jaga-jaga eksplisit -- pastikan tidak ada baris dgn
    # prodi_id kosong/NULL (harusnya sudah ke-handle oleh DEFAULT di atas,
    # tapi kalau kolom sudah pernah ditambah manual tanpa default, ini jaring pengaman).
    def _backfill():
        with engine.begin() as conn:
            r = conn.exec_driver_sql(
                f"UPDATE `{TABLE}` SET prodi_id = '{DEFAULT_PRODI}' WHERE prodi_id IS NULL OR prodi_id = ''"
            )
            return r.rowcount
    ok, n_backfilled = db.with_retry(_backfill, label="backfill prodi_id kosong")
    if ok and n_backfilled:
        print(f"OK -- {n_backfilled} baris existing di-backfill prodi_id='{DEFAULT_PRODI}'.")

    # Langkah 2: ganti UNIQUE KEY
    OLD_KEY = "uq_item_row_col_tahun"
    NEW_KEY = "uq_prodi_item_row_col_tahun"
    if _key_exists(engine, TABLE, NEW_KEY):
        print(f"SKIP -- UNIQUE KEY {NEW_KEY} sudah ada di {TABLE}.")
    else:
        def _swap_key():
            with engine.begin() as conn:
                if _key_exists(engine, TABLE, OLD_KEY):
                    conn.exec_driver_sql(f"ALTER TABLE `{TABLE}` DROP INDEX `{OLD_KEY}`")
                conn.exec_driver_sql(
                    f"ALTER TABLE `{TABLE}` ADD UNIQUE KEY `{NEW_KEY}` "
                    f"(`prodi_id`, `item_id`, `baris_ke`, `kolom`, `tahun`)"
                )
        ok, _ = db.with_retry(_swap_key, label="ganti UNIQUE KEY jadi (prodi_id, item_id, baris_ke, kolom, tahun)")
        if not ok:
            raise SystemExit("GAGAL mengganti UNIQUE KEY -- batal.")
        print(f"OK -- UNIQUE KEY diganti jadi ({', '.join(['prodi_id', 'item_id', 'baris_ke', 'kolom', 'tahun'])}).")

    with engine.connect() as conn:
        r = conn.exec_driver_sql(f"SHOW CREATE TABLE `{TABLE}`")
        print("\n--- Skema akhir ---")
        print(r.fetchone()[1])


if __name__ == "__main__":
    main()
