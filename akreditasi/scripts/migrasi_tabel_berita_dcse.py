"""Migrasi tabel akreditasi_berita_dcse -- Fase 2 Bagian B poin 3
(pipeline arsip berita dcse.fmipa.ugm.ac.id). Idempoten.

Jalankan sekali sebelum pakai pipeline_dcse_berita.py:
    ..\\venv\\Scripts\\python.exe scripts\\migrasi_tabel_berita_dcse.py
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

import db  # noqa: E402

DDL = f"""
CREATE TABLE IF NOT EXISTS `{db.t('berita_dcse')}` (
    url VARCHAR(500) PRIMARY KEY,
    judul TEXT,
    tanggal VARCHAR(40),
    deskripsi TEXT,
    kategori TEXT,
    relevan_mei TINYINT(1) NOT NULL DEFAULT 0,
    fetched_at DATETIME,
    INDEX idx_relevan_mei (relevan_mei)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4
"""


def main() -> None:
    engine = db.get_engine()

    def _run() -> None:
        with engine.begin() as conn:
            conn.exec_driver_sql(DDL)

    ok, _ = db.with_retry(_run, label="migrasi akreditasi_berita_dcse")
    if not ok:
        raise SystemExit("Gagal migrasi tabel akreditasi_berita_dcse -- cek koneksi MySQL.")
    print(f"OK -- tabel {db.t('berita_dcse')} siap.")


if __name__ == "__main__":
    main()
