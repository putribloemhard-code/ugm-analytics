"""Migrasi tabel akreditasi_item_tersedia -- Fase 2 (pelengkap Bagian B):
penyimpanan data live utk 5 item resmi berstatus "tersedia" di
data_source_map.json (identitas_pt_upps_ps, status_akreditasi_seluruh_ps,
led_b2_vmts, lkps_2_b_1, lkps_6). Idempoten.

Skema EAV sama seperti akreditasi_data_manual LAMA (item_id, baris_ke,
kolom, nilai) -- TAPI ini tabel BARU, khusus data yang genuinely ditarik
live oleh pipeline_item_tersedia.py, BUKAN hasil ekstraksi PDF (itu ada
di akreditasi_data_manual_arsip_pdf, tidak dipakai lagi).

Jalankan sekali sebelum pakai pipeline_item_tersedia.py:
    ..\\venv\\Scripts\\python.exe scripts\\migrasi_tabel_item_tersedia.py
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

import db  # noqa: E402

DDL = f"""
CREATE TABLE IF NOT EXISTS `{db.t('item_tersedia')}` (
    item_id VARCHAR(64) NOT NULL,
    baris_ke INT NOT NULL DEFAULT 1,
    kolom VARCHAR(255) NOT NULL,
    nilai TEXT,
    sumber_url VARCHAR(500),
    fetched_at DATETIME,
    PRIMARY KEY (item_id, baris_ke, kolom)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4
"""


def main() -> None:
    engine = db.get_engine()

    def _run() -> None:
        with engine.begin() as conn:
            conn.exec_driver_sql(DDL)

    ok, _ = db.with_retry(_run, label="migrasi akreditasi_item_tersedia")
    if not ok:
        raise SystemExit("Gagal migrasi tabel akreditasi_item_tersedia -- cek koneksi MySQL.")
    print(f"OK -- tabel {db.t('item_tersedia')} siap.")


if __name__ == "__main__":
    main()
