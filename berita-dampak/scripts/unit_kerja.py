"""Daftar 44 fakultas/sekolah/unit kerja resmi UGM, dipakai tag_unit_kerja.py
untuk mengidentifikasi unit mana yang disebut dalam tiap berita.

Sumber: daftar resmi struktur organisasi UGM per kategori (Fakultas 18,
Sekolah 2, Unit Kerja/Direktorat/Biro/Kantor/Satuan 24 -- total 44),
diberikan langsung oleh pemilik project (bukan hasil scraping).

Key dict = id internal (slug), dipakai sebagai nilai kolom `unit_kerja` di
tabel berita_unit_kerja. `nama` = nama resmi penuh (dipakai sebagai keyword
matching di tag_unit_kerja.py -- lihat catatan "Konvensi matching" di sana).
`kategori` = "Fakultas" | "Sekolah" | "Unit Kerja".
"""

UNIT_KERJA = {
    # ---- Fakultas (18) ----
    "fakultas_farmasi": {"nama": "Fakultas Farmasi", "kategori": "Fakultas"},
    "fakultas_kehutanan": {"nama": "Fakultas Kehutanan", "kategori": "Fakultas"},
    "fakultas_biologi": {"nama": "Fakultas Biologi", "kategori": "Fakultas"},
    "fakultas_mipa": {
        "nama": "Fakultas Matematika dan Ilmu Pengetahuan Alam",
        "kategori": "Fakultas",
    },
    "fakultas_filsafat": {"nama": "Fakultas Filsafat", "kategori": "Fakultas"},
    "fakultas_pertanian": {"nama": "Fakultas Pertanian", "kategori": "Fakultas"},
    "fakultas_peternakan": {"nama": "Fakultas Peternakan", "kategori": "Fakultas"},
    "fakultas_psikologi": {"nama": "Fakultas Psikologi", "kategori": "Fakultas"},
    "fakultas_teknologi_pertanian": {
        "nama": "Fakultas Teknologi Pertanian", "kategori": "Fakultas",
    },
    "fakultas_ekonomika_bisnis": {
        "nama": "Fakultas Ekonomika dan Bisnis", "kategori": "Fakultas",
    },
    "fakultas_geografi": {"nama": "Fakultas Geografi", "kategori": "Fakultas"},
    "fakultas_hukum": {"nama": "Fakultas Hukum", "kategori": "Fakultas"},
    "fakultas_teknik": {"nama": "Fakultas Teknik", "kategori": "Fakultas"},
    "fakultas_ilmu_budaya": {"nama": "Fakultas Ilmu Budaya", "kategori": "Fakultas"},
    "fakultas_kedokteran_gigi": {
        "nama": "Fakultas Kedokteran Gigi", "kategori": "Fakultas",
    },
    "fakultas_isipol": {
        "nama": "Fakultas Ilmu Sosial dan Ilmu Politik", "kategori": "Fakultas",
    },
    "fakultas_kedokteran_kmk": {
        "nama": "Fakultas Kedokteran, Kesehatan Masyarakat dan Keperawatan",
        "kategori": "Fakultas",
    },
    "fakultas_kedokteran_hewan": {
        "nama": "Fakultas Kedokteran Hewan", "kategori": "Fakultas",
    },
    # ---- Sekolah (2) ----
    "sekolah_vokasi": {"nama": "Sekolah Vokasi", "kategori": "Sekolah"},
    "sekolah_pascasarjana": {"nama": "Sekolah Pascasarjana", "kategori": "Sekolah"},
    # ---- Unit Kerja / Direktorat / Biro / Kantor / Satuan (24) ----
    "dir_pendidikan_pengajaran": {
        "nama": "Direktorat Pendidikan dan Pengajaran", "kategori": "Unit Kerja",
    },
    "dir_kajian_inovasi_akademik": {
        "nama": "Direktorat Kajian dan Inovasi Akademik", "kategori": "Unit Kerja",
    },
    "perpustakaan_arsip": {"nama": "Perpustakaan dan Arsip", "kategori": "Unit Kerja"},
    "dir_penelitian": {"nama": "Direktorat Penelitian", "kategori": "Unit Kerja"},
    "dir_pengembangan_usaha": {
        "nama": "Direktorat Pengembangan Usaha", "kategori": "Unit Kerja",
    },
    "dir_kemitraan_relasi_global": {
        "nama": "Direktorat Kemitraan dan Relasi Global", "kategori": "Unit Kerja",
    },
    "manajemen_lab_terpadu": {
        "nama": "Manajemen Laboratorium Terpadu", "kategori": "Unit Kerja",
    },
    "dir_kemahasiswaan": {"nama": "Direktorat Kemahasiswaan", "kategori": "Unit Kerja"},
    "dir_pengabdian_masyarakat": {
        "nama": "Direktorat Pengabdian kepada Masyarakat", "kategori": "Unit Kerja",
    },
    "kantor_alumni": {"nama": "Kantor Alumni", "kategori": "Unit Kerja"},
    "dir_sdm": {"nama": "Direktorat Sumber Daya Manusia", "kategori": "Unit Kerja"},
    "dir_keuangan": {"nama": "Direktorat Keuangan", "kategori": "Unit Kerja"},
    "kantor_pengadaan": {"nama": "Kantor Pengadaan", "kategori": "Unit Kerja"},
    "dir_perencanaan": {"nama": "Direktorat Perencanaan", "kategori": "Unit Kerja"},
    "dir_aset": {"nama": "Direktorat Aset", "kategori": "Unit Kerja"},
    "dir_ti": {"nama": "Direktorat Teknologi Informasi", "kategori": "Unit Kerja"},
    "kantor_k3l": {
        "nama": "Kantor Keamanan Keselamatan Kerja Kedaruratan dan Lingkungan",
        "kategori": "Unit Kerja",
    },
    "sekretariat_universitas": {
        "nama": "Sekretariat Universitas", "kategori": "Unit Kerja",
    },
    "biro_manajemen_strategis": {
        "nama": "Biro Manajemen Strategis", "kategori": "Unit Kerja",
    },
    "biro_hukum_organisasi": {
        "nama": "Biro Hukum dan Organisasi", "kategori": "Unit Kerja",
    },
    "biro_transformasi_digital": {
        "nama": "Biro Transformasi Digital", "kategori": "Unit Kerja",
    },
    "biro_pelayanan_kesehatan_terpadu": {
        "nama": "Biro Pelayanan Kesehatan Terpadu", "kategori": "Unit Kerja",
    },
    "satuan_pengawas_internal": {
        "nama": "Satuan Pengawas Internal", "kategori": "Unit Kerja",
    },
    "satuan_penjaminan_mutu": {
        "nama": "Satuan Penjaminan Mutu dan Reputasi Universitas",
        "kategori": "Unit Kerja",
    },
}

assert len(UNIT_KERJA) == 44, f"Harus 44 unit, ada {len(UNIT_KERJA)}"
