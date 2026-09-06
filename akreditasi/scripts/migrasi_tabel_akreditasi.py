"""Migrasi tabel MySQL untuk subproyek akreditasi. Idempoten -- aman
dijalankan berkali-kali (CREATE TABLE IF NOT EXISTS).

Jalankan sekali sebelum pakai dashboard:
    ..\\venv\\Scripts\\python.exe scripts\\migrasi_tabel_akreditasi.py

Tabel yang dibuat:
- akreditasi_data_manual: penyimpanan generic untuk SEMUA item registry
  berstatus "perlu_input_manual" (lihat registry_kebutuhan_data.py). Skema
  "long"/EAV (satu baris = satu sel), bukan satu tabel per item LKPS --
  supaya satu tabel bisa menampung 33 jenis item data yang kolomnya
  berbeda-beda tanpa migrasi skema tiap kali ada item baru.

  Kolom `baris_ke` adalah TAMBAHAN di luar spesifikasi awal (id, item_id,
  kolom, nilai, tahun, link_bukti, diisi_oleh, updated_at) -- diperlukan
  karena banyak tabel LKPS multi-baris (mis. "3.A.2 per judul penelitian",
  "3.C.1 per kontrak kerja sama"); tanpa ini tidak mungkin merekonstruksi
  baris mana yang berpasangan dengan baris mana saat baca balik ke
  st.data_editor / generate_template.py.
"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

import db  # noqa: E402

DDL = f"""
CREATE TABLE IF NOT EXISTS `{db.t('data_manual')}` (
    id INT AUTO_INCREMENT PRIMARY KEY,
    item_id VARCHAR(64) NOT NULL,
    baris_ke INT NOT NULL DEFAULT 1,
    kolom VARCHAR(255) NOT NULL,
    tahun VARCHAR(16) NULL,
    nilai TEXT,
    link_bukti VARCHAR(1000),
    diisi_oleh VARCHAR(255),
    updated_at DATETIME,
    UNIQUE KEY uq_item_row_col_tahun (item_id, baris_ke, kolom, tahun)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4
"""


def main() -> None:
    engine = db.get_engine()

    def _run() -> None:
        with engine.begin() as conn:
            conn.exec_driver_sql(DDL)

    ok, _ = db.with_retry(_run, label="migrasi akreditasi_data_manual")
    if not ok:
        raise SystemExit("Gagal migrasi tabel akreditasi_data_manual -- cek koneksi MySQL.")
    print(f"OK -- tabel {db.t('data_manual')} siap.")


if __name__ == "__main__":
    main()
