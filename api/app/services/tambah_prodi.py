"""Tambah daftar program studi per fakultas ke portal Akreditasi (padanan "+ Tambah prodi baru").

Memakai AccreditationWorkspaceService.add_program, jadi aturan nama, jenjang, dan slug sama persis
dengan form di /akreditasi. Prodi yang namanya sudah ada di fakultas itu dilewati, jadi aman diulang.

    # server (container api, PostgreSQL)
    docker compose run --rm --entrypoint python api -m app.services.tambah_prodi
    # lokal (MySQL dari .env di root repo), dari folder api/
    python -m app.services.tambah_prodi --mysql-lokal
"""
from __future__ import annotations

import argparse

from sqlalchemy import text

from app.services.accreditation_workspace import AccreditationWorkspaceService, WorkspaceError

# slug fakultas (akreditasi_fakultas.slug) -> [(nama prodi, jenjang)]. Penamaan mengikuti prodi yang
# sudah ada: Sarjana tanpa awalan jenjang, Magister/Doktor dengan awalan.
PRODI: dict[str, list[tuple[str, str]]] = {
    "ftp": [  # Fakultas Teknologi Pertanian (ditambahkan 2026-10-07)
        ("Teknologi Pangan dan Produk Pertanian", "Sarjana"),
        ("Teknik Pertanian", "Sarjana"),
        ("Teknologi Industri Pertanian", "Sarjana"),
        ("Magister Ilmu dan Teknologi Pangan", "Magister"),
        ("Magister Teknologi Hasil Perkebunan", "Magister"),
        ("Magister Teknik Pertanian", "Magister"),
        ("Magister Teknologi Industri Pertanian", "Magister"),
        ("Doktor Ilmu Pangan", "Doktor"),
        ("Doktor Ilmu Teknik Pertanian", "Doktor"),
        ("Doktor Teknologi Industri Pertanian", "Doktor"),
    ],
    "fapet": [  # Fakultas Peternakan (ditambahkan 2026-10-07, daftar dari pengguna)
        ("Ilmu dan Industri Peternakan", "Sarjana"),
        ("Profesi Insinyur Peternakan", "Profesi"),
        ("Magister Ilmu Peternakan", "Magister"),
        ("Doktor Ilmu Peternakan", "Doktor"),
    ],
    # Fakultas lain: dari data kurikulum matkul-sustainability/data/Deskripsi Matkul Kepmen.csv
    # (2026-10-07), nama dirapikan ke pola di atas. MIPA & FTP dilewati (sudah terisi; nama di CSV
    # berbeda sehingga akan dobel). Daftar per fakultas belum tentu lengkap -- hanya prodi yang ada di CSV.
    "biologi": [  # Fakultas Biologi
        ("Biologi", "Sarjana"),
        ("Profesi Kurator Keanekaragaman Hayati", "Profesi"),
        ("Magister Biologi", "Magister"),
        ("Doktor Ilmu Biologi", "Doktor"),
    ],
    "faperta": [  # Fakultas Pertanian
        ("Mikrobiologi Pertanian", "Sarjana"),
        ("Teknologi Hasil Perikanan", "Sarjana"),
        ("Magister Agronomi", "Magister"),
        ("Magister Ekonomi Pertanian", "Magister"),
        ("Magister Fitopatologi", "Magister"),
        ("Magister Ilmu Hama Tanaman", "Magister"),
        ("Magister Ilmu Perikanan", "Magister"),
        ("Magister Ilmu Tanah", "Magister"),
        ("Magister Manajemen Agribisnis", "Magister"),
        ("Magister Pemuliaan Tanaman", "Magister"),
        ("Doktor Ilmu Pertanian", "Doktor"),
    ],
    "farmasi": [  # Fakultas Farmasi
        ("Farmasi", "Sarjana"),
        ("Profesi Apoteker", "Profesi"),
        ("Magister Farmasi Klinik", "Magister"),
        ("Magister Ilmu Farmasi", "Magister"),
        ("Magister Manajemen Farmasi", "Magister"),
        ("Doktor Ilmu Farmasi", "Doktor"),
    ],
    "feb": [  # Fakultas Ekonomika dan Bisnis
        ("Akuntansi", "Sarjana"),
        ("Ilmu Ekonomi", "Sarjana"),
        ("Manajemen", "Sarjana"),
        ("ASEAN Master in Sustainability Management (AMSM)", "Magister"),
        ("Magister Akuntansi", "Magister"),
        ("Magister Ekonomika Pembangunan", "Magister"),
        ("Magister Manajemen", "Magister"),
        ("Magister Sains Ilmu Akuntansi", "Magister"),
        ("Magister Sains Ilmu Ekonomi", "Magister"),
        ("Magister Sains Ilmu Manajemen", "Magister"),
        ("Doktor Ilmu Akuntansi", "Doktor"),
        ("Doktor Ilmu Ekonomi", "Doktor"),
        ("Doktor Ilmu Manajemen", "Doktor"),
    ],
    "fh": [  # Fakultas Hukum
        ("Ilmu Hukum", "Sarjana"),
        ("Magister Hukum Kesehatan", "Magister"),
        ("Magister Hukum Litigasi", "Magister"),
        ("Magister Hukum dan Kenegaraan", "Magister"),
        ("Magister Ilmu Hukum", "Magister"),
        ("Magister Kenotariatan", "Magister"),
        ("The Master in Law (LLM) Program", "Magister"),
        ("Doktor Ilmu Hukum", "Doktor"),
    ],
    "fib": [  # Fakultas Ilmu Budaya
        ("Antropologi Budaya", "Sarjana"),
        ("Arkeologi", "Sarjana"),
        ("Bahasa dan Kebudayaan Jepang", "Sarjana"),
        ("Bahasa dan Kebudayaan Korea", "Sarjana"),
        ("Bahasa dan Sastra Indonesia", "Sarjana"),
        ("Bahasa dan Sastra Prancis", "Sarjana"),
        ("Bahasa, Sastra, dan Budaya Jawa", "Sarjana"),
        ("Ilmu Sejarah", "Sarjana"),
        ("Pariwisata", "Sarjana"),
        ("Sastra Arab", "Sarjana"),
        ("Sastra Inggris", "Sarjana"),
        ("Magister Antropologi", "Magister"),
        ("Magister Arkeologi", "Magister"),
        ("Magister Kajian Budaya Timur Tengah", "Magister"),
        ("Magister Linguistik", "Magister"),
        ("Magister Pengkajian Amerika", "Magister"),
        ("Magister Sastra", "Magister"),
        ("Magister Sejarah", "Magister"),
    ],
    "filsafat": [  # Fakultas Filsafat
        ("Filsafat", "Sarjana"),
        ("Magister Filsafat", "Magister"),
        ("Doktor Filsafat", "Doktor"),
    ],
    "fisipol": [  # Fakultas Ilmu Sosial dan Ilmu Politik
        ("Ilmu Hubungan Internasional", "Sarjana"),
        ("Ilmu Komunikasi", "Sarjana"),
        ("Manajemen dan Kebijakan Publik", "Sarjana"),
        ("Pembangunan Sosial dan Kesejahteraan", "Sarjana"),
        ("Politik dan Pemerintahan", "Sarjana"),
        ("Sosiologi", "Sarjana"),
        ("Magister Ilmu Administrasi Publik", "Magister"),
        ("Magister Ilmu Hubungan Internasional", "Magister"),
        ("Magister Ilmu Komunikasi", "Magister"),
        ("Magister Ilmu Politik dan Pemerintahan", "Magister"),
        ("Magister Manajemen dan Kebijakan Publik", "Magister"),
        ("Magister Pembangunan Sosial dan Kesejahteraan", "Magister"),
        ("Magister Sosiologi", "Magister"),
        ("Doktor Ilmu Administrasi Publik", "Doktor"),
        ("Doktor Ilmu Komunikasi", "Doktor"),
        ("Doktor Ilmu Politik dan Pemerintahan", "Doktor"),
        ("Doktor Manajemen dan Kebijakan Publik", "Doktor"),
        ("Doktor Pembangunan Sosial dan Kesejahteraan", "Doktor"),
        ("Doktor Sosiologi", "Doktor"),
    ],
    "fkg": [  # Fakultas Kedokteran Gigi
        ("Higiene Gigi", "Sarjana"),
        ("Pendidikan Kedokteran Gigi", "Sarjana"),
        ("Profesi Kedokteran Gigi", "Profesi"),
        ("Spesialis Bedah Mulut dan Maksilofasial", "Spesialis"),
        ("Spesialis Kedokteran Gigi Anak", "Spesialis"),
        ("Spesialis Konservasi Gigi", "Spesialis"),
        ("Spesialis Ortodonsia", "Spesialis"),
        ("Spesialis Penyakit Mulut", "Spesialis"),
        ("Spesialis Periodonsia", "Spesialis"),
        ("Spesialis Prostodonsia", "Spesialis"),
        ("Magister Ilmu Kedokteran Gigi", "Magister"),
        ("Magister Ilmu Kedokteran Gigi Klinis", "Magister"),
        ("Doktor Ilmu Kedokteran Gigi", "Doktor"),
    ],
    "fkh": [  # Fakultas Kedokteran Hewan
        ("Kedokteran Hewan", "Sarjana"),
        ("Dokter Hewan", "Profesi"),
    ],
    "fkkmk": [  # Fakultas Kedokteran, Kesehatan Masyarakat, dan Keperawatan
        ("Gizi Kesehatan", "Sarjana"),
        ("Kedokteran", "Sarjana"),
        ("Magister Kebijakan dan Manajemen Kesehatan", "Magister"),
        ("Magister Kedokteran Tropis", "Magister"),
        ("Magister Kesehatan Masyarakat", "Magister"),
    ],
    "ft": [  # Fakultas Teknik
        ("Arsitektur", "Sarjana"),
        ("Perencanaan Wilayah dan Kota", "Sarjana"),
        ("Teknik Biomedis", "Sarjana"),
        ("Teknik Elektro", "Sarjana"),
        ("Teknik Fisika", "Sarjana"),
        ("Teknik Geodesi", "Sarjana"),
        ("Teknik Geologi", "Sarjana"),
        ("Teknik Industri", "Sarjana"),
        ("Teknik Infrastruktur Lingkungan", "Sarjana"),
        ("Teknik Kimia", "Sarjana"),
        ("Teknik Mesin", "Sarjana"),
        ("Teknik Nuklir", "Sarjana"),
        ("Teknik Sipil", "Sarjana"),
        ("Teknik Sumber Daya Air", "Sarjana"),
        ("Teknologi Informasi", "Sarjana"),
        ("Magister Arsitektur", "Magister"),
        ("Magister Perencanaan Wilayah dan Kota", "Magister"),
        ("Magister Rancang Kota", "Magister"),
        ("Magister Sistem dan Teknik Transportasi", "Magister"),
        ("Magister Teknik Elektro", "Magister"),
        ("Magister Teknik Geologi", "Magister"),
        ("Magister Teknik Geomatika", "Magister"),
        ("Magister Teknik Industri", "Magister"),
        ("Magister Teknik Kimia", "Magister"),
        ("Magister Teknik Mesin", "Magister"),
        ("Magister Teknik Pengelolaan Bencana Alam", "Magister"),
        ("Magister Teknik Sipil", "Magister"),
        ("Magister Teknik Sistem", "Magister"),
        ("Magister Teknologi Informasi", "Magister"),
        ("Pendidikan Profesi Arsitek", "Profesi"),
        ("Doktor Perencanaan Wilayah dan Kota", "Doktor"),
        ("Program Profesi Insinyur", "Profesi"),
        ("Doktor Teknik Elektro", "Doktor"),
        ("Doktor Teknik Geologi", "Doktor"),
        ("Doktor Teknik Geomatika", "Doktor"),
        ("Doktor Teknik Industri", "Doktor"),
        ("Doktor Teknik Mesin", "Doktor"),
    ],
    "geografi": [  # Fakultas Geografi
        ("Geografi Lingkungan", "Sarjana"),
        ("Kartografi dan Penginderaan Jauh", "Sarjana"),
        ("Pembangunan Wilayah", "Sarjana"),
        ("Magister Geografi", "Magister"),
        ("Magister Penginderaan Jauh", "Magister"),
        ("Doktor Ilmu Geografi", "Doktor"),
    ],
    "kehutanan": [  # Fakultas Kehutanan
        ("Kehutanan", "Sarjana"),
        ("Magister Ilmu Kehutanan", "Magister"),
        ("Doktor Ilmu Kehutanan", "Doktor"),
    ],
    "psikologi": [  # Fakultas Psikologi
        ("Psikologi", "Sarjana"),
        ("Magister Psikologi", "Magister"),
        ("Doktor Ilmu Psikologi", "Doktor"),
    ],
    "sps": [  # Sekolah Pascasarjana
        ("Magister Bioetika", "Magister"),
        ("Magister Bioteknologi", "Magister"),
        ("Magister Ilmu Lingkungan", "Magister"),
        ("Magister Kajian Budaya dan Media", "Magister"),
        ("Magister Kependudukan", "Magister"),
        ("Magister Pengkajian Seni Pertunjukan dan Seni Rupa", "Magister"),
        ("Magister Penyuluhan dan Komunikasi Pembangunan", "Magister"),
        ("Doktor Ilmu Lingkungan", "Doktor"),
        ("Doktor Kajian Budaya dan Media", "Doktor"),
        ("Doktor Kependudukan", "Doktor"),
        ("Doktor Pengkajian Seni Pertunjukan dan Seni Rupa", "Doktor"),
    ],
    "sv": [  # Sekolah Vokasi
        ("Akuntansi Sektor Publik", "Sarjana Terapan"),
        ("Bahasa Inggris", "Sarjana Terapan"),
        ("Bahasa Jepang untuk Komunikasi Bisnis dan Profesional", "Sarjana Terapan"),
        ("Bisnis Perjalanan Wisata", "Sarjana Terapan"),
        ("Manajemen Informasi Kesehatan", "Sarjana Terapan"),
        ("Manajemen dan Penilaian Properti", "Sarjana Terapan"),
        ("Pembangunan Ekonomi Kewilayahan", "Sarjana Terapan"),
        ("Pengelolaan Arsip dan Rekaman Informasi", "Sarjana Terapan"),
        ("Pengelolaan Hutan", "Sarjana Terapan"),
        ("Pengembangan Produk Agroindustri", "Sarjana Terapan"),
        ("Perbankan", "Sarjana Terapan"),
        ("Sistem Informasi Geografis", "Sarjana Terapan"),
        ("Teknik Pengelolaan dan Pemeliharaan Infrastruktur Sipil", "Sarjana Terapan"),
        ("Teknik Pengelolaan dan Perawatan Alat Berat", "Sarjana Terapan"),
        ("Teknologi Rekayasa Elektro", "Sarjana Terapan"),
        ("Teknologi Rekayasa Instrumentasi dan Kontrol", "Sarjana Terapan"),
        ("Teknologi Rekayasa Internet", "Sarjana Terapan"),
        ("Teknologi Rekayasa Mesin", "Sarjana Terapan"),
        ("Teknologi Rekayasa Pelaksanaan Bangunan Sipil", "Sarjana Terapan"),
        ("Teknologi Rekayasa Perangkat Lunak", "Sarjana Terapan"),
        ("Teknologi Survei dan Pemetaan Dasar", "Sarjana Terapan"),
        ("Teknologi Veteriner", "Sarjana Terapan"),
        ("Bahasa Inggris", "Diploma"),
        ("Keselamatan dan Kesehatan Kerja", "Magister Terapan"),
        ("Pengembangan Atraksi Wisata", "Magister Terapan"),
    ],
}


def tambah(engine) -> list[tuple[str, str, str]]:
    """Tambahkan semua PRODI; kembalikan [(fakultas, nama, hasil)] dengan hasil = slug baru / 'sudah ada'."""
    svc = AccreditationWorkspaceService(engine)
    hasil = []
    for slug_fakultas, daftar in PRODI.items():
        with engine.connect() as conn:
            fakultas_id = conn.execute(text("SELECT id FROM akreditasi_fakultas WHERE slug = :s"),
                                       {"s": slug_fakultas}).scalar()
        if fakultas_id is None:
            raise SystemExit(f"Fakultas dengan slug '{slug_fakultas}' tidak ada di akreditasi_fakultas.")
        for nama, jenjang in daftar:
            try:
                hasil.append((slug_fakultas, nama, svc.add_program(fakultas_id, nama, jenjang)["slug"]))
            except WorkspaceError as exc:
                if "sudah ada" not in str(exc):
                    raise
                hasil.append((slug_fakultas, nama, "sudah ada"))
    return hasil


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--mysql-lokal", action="store_true", help="pakai MySQL dari .env root repo (mode laptop)")
    args = parser.parse_args()
    if args.mysql_lokal:
        from app.services.migrasi_kolom_tabel import _engine_mysql_lokal
        engine = _engine_mysql_lokal()
    else:
        from app.db import get_engine
        engine = get_engine()
    for fakultas, nama, slug in tambah(engine):
        print(f"  [{fakultas}] {nama}: {slug}")


if __name__ == "__main__":
    main()
