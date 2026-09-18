"""Migrasi tabel MySQL untuk fitur upload file pendukung akreditasi.
Idempoten -- aman dijalankan berkali-kali (CREATE TABLE IF NOT EXISTS).

Jalankan sekali sebelum pakai fitur upload di halaman /akreditasi:
    ..\\venv\\Scripts\\python.exe scripts\\migrasi_tabel_upload_akreditasi.py

Tabel yang dibuat:
- akreditasi_upload_file: metadata file yang diupload user lewat halaman
  Akreditasi (PDF/Word/Excel) -- BUKAN isi file itu sendiri. File fisik
  disimpan di folder lokal `akreditasi/data/uploads/<prodi_id>/` (lihat
  scripts/upload_akreditasi.py), tabel ini cuma menyimpan pointer + status
  pipeline ekstraksi. Alasan file di folder lokal (bukan BLOB di MySQL):
  ukuran file bisa sampai 25 MB/file (lihat .streamlit/config.toml,
  maxUploadSize) -- BLOB besar di MySQL bikin ukuran backup/replikasi
  membengkak tanpa manfaat query, sedangkan metadata (nama, path, status)
  memang perlu terstruktur & bisa di-join/filter di MySQL sepert tabel lain.

  Kolom `status`: 'belum_diekstrak' (baru diupload) -> 'diekstrak'
  (Tahap 2/3, teks berhasil diambil) -> 'gagal_ekstrak' (error saat proses).
  Ekstraksi ITU SENDIRI (nilai per item registry) TIDAK disimpan di tabel
  ini -- lihat CATATAN kebijakan di registry_kebutuhan_data.py poin 7:
  hasil ekstraksi AI baru boleh masuk `akreditasi_data_manual` SETELAH
  direview & disimpan manual oleh user (Tahap 3), dengan diisi_oleh
  "AI-extraction (perlu verifikasi)" sampai user konfirmasi.
"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

import db  # noqa: E402

DDL = f"""
CREATE TABLE IF NOT EXISTS `{db.t('upload_file')}` (
    id INT AUTO_INCREMENT PRIMARY KEY,
    prodi_id VARCHAR(64) NOT NULL,
    nama_file VARCHAR(500) NOT NULL,
    path_lokal VARCHAR(1000) NOT NULL,
    tipe_file VARCHAR(16) NOT NULL,
    ukuran_bytes INT NOT NULL,
    status VARCHAR(32) NOT NULL DEFAULT 'belum_diekstrak',
    diupload_oleh VARCHAR(255),
    uploaded_at DATETIME NOT NULL,
    diekstrak_at DATETIME NULL,
    KEY idx_prodi (prodi_id)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4
"""


def main() -> None:
    engine = db.get_engine()

    def _run() -> None:
        with engine.begin() as conn:
            conn.exec_driver_sql(DDL)

    ok, _ = db.with_retry(_run, label="migrasi akreditasi_upload_file")
    if not ok:
        raise SystemExit("Gagal migrasi tabel akreditasi_upload_file -- cek koneksi MySQL.")
    print(f"OK -- tabel {db.t('upload_file')} siap.")


if __name__ == "__main__":
    main()
