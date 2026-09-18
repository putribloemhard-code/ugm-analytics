"""Migrasi tabel akreditasi_publikasi_dosen -- Fase 2 Bagian B poin 1
(pipeline SINTA). Idempoten -- aman dijalankan berkali-kali.

Jalankan sekali sebelum pakai pipeline_sinta.py:
    ..\\venv\\Scripts\\python.exe scripts\\migrasi_tabel_publikasi_dosen.py
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

import db  # noqa: E402

DDL = f"""
CREATE TABLE IF NOT EXISTS `{db.t('publikasi_dosen')}` (
    link VARCHAR(500) PRIMARY KEY,
    dosen VARCHAR(255) NOT NULL,
    sinta_id VARCHAR(20) NOT NULL,
    platform VARCHAR(20) NOT NULL DEFAULT 'scopus',
    judul TEXT,
    tahun VARCHAR(8),
    sumber VARCHAR(255),
    fetched_at DATETIME,
    INDEX idx_sinta_id (sinta_id)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4
"""


def main() -> None:
    engine = db.get_engine()

    def _run() -> None:
        with engine.begin() as conn:
            conn.exec_driver_sql(DDL)

    ok, _ = db.with_retry(_run, label="migrasi akreditasi_publikasi_dosen")
    if not ok:
        raise SystemExit("Gagal migrasi tabel akreditasi_publikasi_dosen -- cek koneksi MySQL.")
    print(f"OK -- tabel {db.t('publikasi_dosen')} siap.")


if __name__ == "__main__":
    main()
