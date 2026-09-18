"""Migrasi tabel MySQL untuk hasil ekstraksi AI dari file upload akreditasi
(Tahap 3 -- lihat scripts/ekstraksi_akreditasi.py). Idempoten.

Jalankan sekali:
    ..\\venv\\Scripts\\python.exe scripts\\migrasi_tabel_ekstraksi_akreditasi.py

Tabel:
- akreditasi_upload_ekstraksi: hasil ekstraksi AI PER FILE PER KOLOM --
  BUKAN pengganti akreditasi_data_manual, cuma tempat penampungan
  sementara SEBELUM user review & konfirmasi manual (lihat kebijakan
  registry_kebutuhan_data.py poin 7 -- data AI TIDAK BOLEH otomatis
  dianggap resmi). Satu (item_id, nama_kolom, baris_ke) bisa punya
  BEBERAPA baris di tabel ini kalau berasal dari file berbeda dengan
  nilai berbeda (konflik) -- UI menampilkan semua ke user, TIDAK
  menimpa otomatis (lihat docstring modul poin 3).

  `dikonfirmasi_at` NULL = masih pending review. Begitu user klik
  Simpan pada satu item, baris ekstraksi utk item itu di-set
  dikonfirmasi_at = now supaya tidak muncul lagi sbg pending.
"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

import db  # noqa: E402

DDL = f"""
CREATE TABLE IF NOT EXISTS `{db.t('upload_ekstraksi')}` (
    id INT AUTO_INCREMENT PRIMARY KEY,
    upload_file_id INT NOT NULL,
    prodi_id VARCHAR(64) NOT NULL,
    item_id VARCHAR(64) NOT NULL,
    baris_ke INT NOT NULL DEFAULT 1,
    nama_kolom VARCHAR(255) NOT NULL,
    nilai TEXT,
    kutipan TEXT,
    created_at DATETIME NOT NULL,
    dikonfirmasi_at DATETIME NULL,
    KEY idx_prodi_item (prodi_id, item_id),
    KEY idx_upload (upload_file_id)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4
"""


def main() -> None:
    engine = db.get_engine()

    def _run() -> None:
        with engine.begin() as conn:
            conn.exec_driver_sql(DDL)

    ok, _ = db.with_retry(_run, label="migrasi akreditasi_upload_ekstraksi")
    if not ok:
        raise SystemExit("Gagal migrasi tabel akreditasi_upload_ekstraksi -- cek koneksi MySQL.")
    print(f"OK -- tabel {db.t('upload_ekstraksi')} siap.")


if __name__ == "__main__":
    main()
