"""Migrasi tabel referensi multi-prodi -- Bagian B (fallback dropdown,
BUKAN crawler per fakultas -- keputusan user setelah investigasi Bagian B
menunjukkan 4 pola struktur website berbeda dari 4 fakultas sample,
tidak bisa digeneralisir jadi satu crawler).

Tabel yang dibuat:
- akreditasi_fakultas: 20 fakultas/sekolah UGM, diisi SEKALI dari
  ugm.ac.id/id/fakultas/ (halaman yang sudah divalidasi bisa di-fetch
  polos -- lihat investigasi Bagian B). BUKAN pipeline berkala -- daftar
  fakultas jarang berubah, dijalankan manual kalau memang perlu update.
- akreditasi_prodi: KOSONG dari sononya kecuali 1 baris seed (MEI di
  bawah MIPA, slug "mei" -- SAMA PERSIS dengan prodi_id yang sudah
  dipakai di akreditasi_data_manual, supaya data existing MEI tidak
  berubah). Baris lain diisi manual lewat form "+ Tambah prodi baru" di
  UI /akreditasi, BUKAN hasil crawl otomatis.

Idempoten -- aman dijalankan berkali-kali (CREATE TABLE IF NOT EXISTS +
INSERT IGNORE berbasis slug unik).

Jalankan sekali:
    ..\\venv\\Scripts\\python.exe scripts\\migrasi_tabel_prodi.py
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

import db  # noqa: E402

DDL_FAKULTAS = f"""
CREATE TABLE IF NOT EXISTS `{db.t('fakultas')}` (
    id INT AUTO_INCREMENT PRIMARY KEY,
    nama VARCHAR(255) NOT NULL,
    slug VARCHAR(64) NOT NULL,
    url VARCHAR(500),
    UNIQUE KEY uq_slug (slug)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4
"""

DDL_PRODI = f"""
CREATE TABLE IF NOT EXISTS `{db.t('prodi')}` (
    id INT AUTO_INCREMENT PRIMARY KEY,
    fakultas_id INT NOT NULL,
    nama VARCHAR(255) NOT NULL,
    jenjang VARCHAR(32) NOT NULL,
    slug VARCHAR(64) NOT NULL,
    url VARCHAR(500),
    UNIQUE KEY uq_slug (slug),
    KEY idx_fakultas (fakultas_id),
    CONSTRAINT fk_prodi_fakultas FOREIGN KEY (fakultas_id) REFERENCES `{db.t('fakultas')}` (id)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4
"""

# 20 fakultas/sekolah -- diambil 2026-09-11 dari ugm.ac.id/id/fakultas/
# (nama, slug, url). Slug singkatan umum UGM, BUKAN hasil ekstraksi
# otomatis dari URL (URL-nya sendiri panjang & deskriptif, mis.
# ".../fakultas-matematika-dan-ilmu-pengetahuan-alam/").
FAKULTAS = [
    ("Fakultas Kehutanan", "kehutanan",
     "https://ugm.ac.id/id/fakultas/fakultas-kehutanan/"),
    ("Fakultas Kedokteran, Kesehatan Masyarakat, dan Keperawatan", "fkkmk",
     "https://ugm.ac.id/id/fakultas/fakultas-kedokteran-kesehatan-masyarakat-dan-keperawatan/"),
    ("Fakultas Kedokteran Hewan", "fkh",
     "https://ugm.ac.id/id/fakultas/fakultas-kedokteran-hewan/"),
    ("Fakultas Kedokteran Gigi", "fkg",
     "https://ugm.ac.id/id/fakultas/fakultas-kedokteran-gigi/"),
    ("Fakultas Ilmu Sosial dan Ilmu Politik", "fisipol",
     "https://ugm.ac.id/id/fakultas/fakultas-ilmu-sosial-dan-ilmu-politik/"),
    ("Fakultas Ilmu Budaya", "fib",
     "https://ugm.ac.id/id/fakultas/fakultas-ilmu-budaya/"),
    ("Fakultas Hukum", "fh",
     "https://ugm.ac.id/id/fakultas/fakultas-hukum/"),
    ("Fakultas Matematika dan Ilmu Pengetahuan Alam", "mipa",
     "https://ugm.ac.id/id/fakultas/fakultas-matematika-dan-ilmu-pengetahuan-alam/"),
    ("Fakultas Pertanian", "faperta",
     "https://ugm.ac.id/id/fakultas/fakultas-pertanian/"),
    ("Fakultas Peternakan", "fapet",
     "https://ugm.ac.id/id/fakultas/fakultas-peternakan/"),
    ("Fakultas Psikologi", "psikologi",
     "https://ugm.ac.id/id/fakultas/fakultas-psikologi/"),
    ("Fakultas Teknik", "ft",
     "https://ugm.ac.id/id/fakultas/fakultas-teknik/"),
    ("Fakultas Teknologi Pertanian", "ftp",
     "https://ugm.ac.id/id/fakultas/fakultas-teknologi-pertanian/"),
    ("Sekolah Pascasarjana", "sps",
     "https://ugm.ac.id/id/fakultas/sekolah-pascasarjana/"),
    ("Sekolah Vokasi", "sv",
     "https://ugm.ac.id/id/fakultas/sekolah-vokasi/"),
    ("Fakultas Geografi", "geografi",
     "https://ugm.ac.id/id/fakultas/fakultas-geografi/"),
    ("Fakultas Filsafat", "filsafat",
     "https://ugm.ac.id/id/fakultas/fakultas-filsafat/"),
    ("Fakultas Farmasi", "farmasi",
     "https://ugm.ac.id/id/fakultas/fakultas-farmasi/"),
    ("Fakultas Ekonomika dan Bisnis", "feb",
     "https://ugm.ac.id/id/fakultas/fakultas-ekonomika-dan-bisnis/"),
    ("Fakultas Biologi", "biologi",
     "https://ugm.ac.id/id/fakultas/fakultas-biologi/"),
]


def main() -> None:
    engine = db.get_engine()

    def _create():
        with engine.begin() as conn:
            conn.exec_driver_sql(DDL_FAKULTAS)
            conn.exec_driver_sql(DDL_PRODI)

    ok, _ = db.with_retry(_create, label="migrasi akreditasi_fakultas + akreditasi_prodi")
    if not ok:
        raise SystemExit("Gagal membuat tabel -- cek koneksi MySQL.")
    print(f"OK -- tabel {db.t('fakultas')} & {db.t('prodi')} siap.")

    saved = db.upsert(
        engine, db.t("fakultas"), ["slug", "nama", "url"],
        [(slug, nama, url) for nama, slug, url in FAKULTAS],
        update_columns=["nama", "url"],
        label="upsert fakultas",
    )
    print(f"OK -- {saved} baris fakultas ter-upsert (dari {len(FAKULTAS)} total).")

    # Seed 1 baris MEI -- slug "mei" SAMA PERSIS dgn prodi_id existing di
    # akreditasi_data_manual (lihat migrasi_prodi_id.py), supaya perilaku
    # existing tidak berubah.
    with engine.connect() as conn:
        fakultas_id_mipa = conn.exec_driver_sql(
            f"SELECT id FROM `{db.t('fakultas')}` WHERE slug = 'mipa'"
        ).scalar()
    if not fakultas_id_mipa:
        raise SystemExit("GAGAL -- fakultas MIPA tidak ketemu setelah upsert, cek data FAKULTAS di atas.")

    saved_prodi = db.upsert(
        engine, db.t("prodi"), ["slug", "fakultas_id", "nama", "jenjang"],
        [("mei", fakultas_id_mipa, "Magister Elektronika dan Instrumentasi", "Magister")],
        update_columns=["fakultas_id", "nama", "jenjang"],
        label="upsert prodi seed (MEI)",
    )
    print(f"OK -- {saved_prodi} baris prodi seed ter-upsert (MEI, fakultas_id={fakultas_id_mipa}).")

    with engine.connect() as conn:
        n_fak = conn.exec_driver_sql(f"SELECT COUNT(*) FROM `{db.t('fakultas')}`").scalar()
        n_prodi = conn.exec_driver_sql(f"SELECT COUNT(*) FROM `{db.t('prodi')}`").scalar()
    print(f"Total sekarang: {n_fak} fakultas, {n_prodi} prodi.")


if __name__ == "__main__":
    main()
