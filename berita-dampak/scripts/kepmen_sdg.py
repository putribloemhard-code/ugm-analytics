"""Pemetaan topik dampak berita → Topik Resmi Kepmen 361/M/KEP/2025 → Klaster SDGs.

Sumber: D:\\ugm-analytics\\UGM Analytics.xlsx
- Sheet "Konten UGM Berdampak" baris 6, 8, 9, 10 (baris konten = "Berita").
- Sheet "#Ref" kolom D–F (pemetaan Dampak → Topik Resmi Kepmen → Daftar SDGs).

Dipakai oleh tag_kepmen_berita.py (tagging berita ke Kepmen + SDG)
dan dashboard (tampilan per berita + agregat).
"""

# 17 SDGs — nama resmi (dari sheet #Ref kolom B).
SDG_NAMA = {
    1: "Tanpa Kemiskinan",
    2: "Tanpa Kelaparan",
    3: "Kehidupan Sehat dan Sejahtera",
    4: "Pendidikan Berkualitas",
    5: "Kesetaraan Gender",
    6: "Air Bersih dan Sanitasi Layak",
    7: "Energi Bersih dan Terjangkau",
    8: "Pekerjaan Layak dan Pertumbuhan Ekonomi",
    9: "Industri, Inovasi dan Infrastruktur",
    10: "Berkurangnya Kesenjangan",
    11: "Kota dan Permukiman yang Berkelanjutan",
    12: "Konsumsi dan Produksi yang Bertanggung Jawab",
    13: "Penanganan Perubahan Iklim",
    14: "Ekosistem Lautan",
    15: "Ekosistem Daratan",
    16: "Perdamaian, Keadilan dan Kelembagaan yang Tangguh",
    17: "Kemitraan untuk Mencapai Tujuan",
}

# Topik dampak berita (berita_topik.topik) → metadata Kepmen.
# 'dampak' = pilar (Lingkungan/Sosial/Ekonomi), 'topik_kepmen' = nama resmi
# di sheet Konten UGM Berdampak, 'sdg' = klaster SDGs resmi dari sheet.
# 'indikator'/'formula'/'satuan' = nama + formula indikator resmi sesuai
# Salinan_Kepmen_361_M_KEP_2025_Indikator_Dampak.pdf (hasil OCR:
# docs/kepmen_361_ocr.txt).
TOPIK_KEPMEN = {
    "rehabilitasi_lingkungan": {
        "dampak": "Lingkungan",
        "topik_kepmen": "Keanekaragaman Hayati (Rehabilitasi dan Restorasi Lingkungan)",
        "sdg": [13, 14, 15],
        "indikator": "Jumlah program rehabilitasi dan restorasi lingkungan Perguruan Tinggi",
        "formula": "Jumlah program rehabilitasi dan restorasi lingkungan yang "
                   "dilaksanakan pada periode berjalan (penanaman pohon, "
                   "reboisasi, rehabilitasi lahan kritis, restorasi hutan/"
                   "mangrove/sungai/pesisir, pemulihan kualitas tanah-air-udara, "
                   "konservasi kehati, pengendalian erosi/banjir, ruang "
                   "terbuka hijau, dll).",
        "satuan": "Program",
    },
    "kewirausahaan": {
        "dampak": "Ekonomi",
        "topik_kepmen": "Ekosistem Kewirausahaan",
        "sdg": [8, 9],
        "indikator": "Jumlah entitas spin-off atau start-up dari Perguruan Tinggi yang masih aktif",
        "formula": "Jumlah entitas spin-off/start-up yang dibentuk dari hasil "
                   "riset, inovasi, teknologi, atau proses inkubasi PT dan "
                   "masih aktif beroperasi pada tahun pelaporan.",
        "satuan": "Entitas",
    },
    "kunjungan_akademik": {
        "dampak": "Ekonomi",
        "topik_kepmen": "Kunjungan Akademik dan Pengeluaran Pengunjung",
        "sdg": [8, 11],
        "indikator": "Jumlah pengeluaran pengunjung kegiatan akademik",
        "formula": "Rata-rata pengeluaran per pengunjung (Rp) x Jumlah "
                   "Pengunjung Kegiatan Akademik (wisuda, seminar/konferensi, "
                   "lomba/festival, kunjungan akademik, gathering alumni; "
                   "belanja akomodasi, makanan, transportasi, atraksi, retail).",
        "satuan": "Rupiah (Rp)",
    },
    "kolaborasi_riset": {
        "dampak": "Ekonomi",
        "topik_kepmen": "Penelitian dan Pertukaran Pengetahuan",
        "sdg": [9, 17],
        "indikator": "Jumlah pendapatan yang diterima Perguruan Tinggi dari "
                     "hilirisasi hasil riset dan/atau spin-off dengan industri "
                     "dan pemerintah",
        "formula": "Jumlah pendapatan dari hilirisasi riset / paten / prototipe "
                   "/ HKI / spin-off pada periode berjalan (lisensi, royalti, "
                   "penjualan prototipe, kerja sama pemanfaatan hasil riset).",
        "satuan": "Rupiah (Rp)",
    },
}


def sdg_label(sdg: int) -> str:
    """Label ringkas: 'SDG 13 — Penanganan Perubahan Iklim'."""
    return f"SDG {sdg} — {SDG_NAMA[sdg]}"


# ---- Tema Kepmen lengkap (eksplorasi berita di luar 4 topik inti) ----
# Semua tema resmi Kepmen 361/M/KEP/2025 per pilar. 4 topik inti berita
# (TOPIK_KEPMEN di atas) adalah subset. Keyword dipakai untuk menandai berita
# yang ADA di tabel berita — bukan untuk fetch baru.
# sdg: klaster SDGs dari sheet "#Ref" (kolom E→F, satu topik bisa berlanjut
# ke beberapa baris F di bawahnya). Sumber per topik dicatat di komentar.
TEMA_KEPMEN_LENGKAP = {
    # ---- Dampak Sosial ----
    "pendidikan_inklusif": {
        "dampak": "Sosial",
        "topik_kepmen": "Pendidikan Inklusif",
        "sdg": [1, 4, 10],  # #Ref E3 (F3=(4), F4=(10), F5=(1)); Konten D7=(1),(4),(10)
        "keywords": ["pendidikan inklusif", "pendidikan inklusi", "inklusi",
                     "afirmasi", "disabilitas", "difabel", "penyandang disabilitas",
                     "daerah tertinggal", "daerah 3t", "kip kuliah",
                     "beasiswa afirmasi", "kelompok afirmasi",
                     "inclusive education", "kampus inklusif"],
        "indikator": "Persentase lulusan/mahasiswa kelompok afirmasi yang "
                     "terserap kerja/wirausaha/studi lanjut atau penerima beasiswa internal",
        "formula": "Total lulusan kelompok afirmasi yang bekerja/wirausaha/studi "
                   "lanjut dibagi total lulusan kelompok afirmasi × 100%",
        "satuan": "% (Persentase)",
    },
    "penelitian_inovasi_sosial": {
        "dampak": "Sosial",
        "topik_kepmen": "Penelitian dan Inovasi",
        "sdg": [1, 9],  # #Ref E6 "Penelitian dan inovasi (dimanfaatkan masyarakat rentan)" → F6=(9), F7=(1)
        "keywords": ["hasil riset", "pemanfaatan riset", "masyarakat rentan",
                     "teknologi tepat guna", "inovasi", "hilirisasi",
                     "riset untuk masyarakat", "penelitian terapan",
                     "applied research", "riset dampak", "impact research",
                     "science for society", "riset inovasi"],
        "indikator": "Persentase hasil riset perguruan tinggi yang dimanfaatkan "
                     "oleh masyarakat rentan dan/atau wilayah prioritas pembangunan",
        "formula": "Jumlah hasil riset yang dimanfaatkan ÷ total hasil riset pada "
                   "periode berjalan × 100%",
        "satuan": "% (Persentase)",
    },
    "pengabdian_masyarakat": {
        "dampak": "Sosial",
        "topik_kepmen": "Pengabdian dan Pengembangan Masyarakat",
        "sdg": [1, 8, 11, 17],  # #Ref E8 (8,1,11) + E9 desa binaan (1,11) + Konten D5 desa binaan (1,11,17)
        "keywords": ["pengabdian", "pengembangan masyarakat", "kuliah kerja nyata",
                     "kkn", "desa binaan", "pemberdayaan", "penyuluhan",
                     "pendampingan", "produk inovasi", "umkm",
                     "community service", "community empowerment",
                     "pengabdian masyarakat", "pemberdayaan masyarakat"],
        "indikator": "Jumlah produk inovasi PT yang digunakan oleh UMKM lokal; "
                     "total dana pengabdian masyarakat",
        "formula": "Jumlah seluruh produk inovasi yang digunakan UMKM lokal pada "
                   "periode berjalan (satuan: Produk)",
        "satuan": "Produk",
    },
    "instansi_publik": {
        "dampak": "Sosial",
        "topik_kepmen": "Kontribusi terhadap Instansi Publik",
        "sdg": [16, 17],  # #Ref E11 "Kebijakan publik (pendampingan instansi)" → F11=(16), F12=(17)
        "keywords": ["pendampingan instansi", "instansi publik", "pemerintah daerah",
                     "kebijakan publik", "tata kelola", "perangkat daerah",
                     "pendampingan pemerintah", "asistensi", "pemda",
                     "local government", "pemerintah kabupaten",
                     "pemerintah provinsi", "kementerian", "regulasi"],
        "indikator": "Jumlah instansi publik yang menerima pendampingan dari PT",
        "formula": "Jumlah instansi publik yang menerima pendampingan pada "
                   "periode berjalan",
        "satuan": "Instansi publik",
    },
    # ---- Dampak Ekonomi (di luar 4 topik inti) ----
    "pengajaran_pembelajaran": {
        "dampak": "Ekonomi",
        "topik_kepmen": "Pengajaran dan Pembelajaran",
        "sdg": [8],  # #Ref E13 "Pengajaran dan pembelajaran (pengeluaran mahasiswa)" → F13=(8)
        "keywords": ["pengeluaran mahasiswa", "biaya hidup mahasiswa",
                     "konsumsi mahasiswa", "transportasi mahasiswa",
                     "uang saku mahasiswa", "belanja mahasiswa",
                     "student spending", "cost of living"],
        "indikator": "Jumlah pengeluaran mahasiswa terkait transportasi dan konsumsi harian",
        "formula": "Rata-rata pengeluaran per mahasiswa per bulan × jumlah "
                   "mahasiswa aktif × 12",
        "satuan": "Rupiah (Rp)",
    },
    "belanja_umkm": {
        "dampak": "Ekonomi",
        "topik_kepmen": "Pengeluaran Institusi",
        "sdg": [8, 12],  # #Ref E20 "Pengeluaran institusi (belanja UMKM lokal)" → F20=(8), F21=(12)
        "keywords": ["umkm lokal", "belanja umkm", "katering", "pengadaan barang",
                     "produk lokal", "usaha mikro", "usaha kecil", "pengadaan jasa",
                     "pembelian produk umkm", "local product", "bazar umkm",
                     "pasar umkm", "pemberdayaan umkm", "smes"],
        "indikator": "Jumlah belanja yang dikeluarkan PT untuk UMKM lokal",
        "formula": "Jumlah nilai belanja pengadaan barang/jasa kepada UMKM lokal "
                   "pada tahun pelaporan",
        "satuan": "Rupiah (Rp)",
    },
    # ---- Dampak Lingkungan (di luar 4 topik inti) ----
    "energi": {
        "dampak": "Lingkungan",
        "topik_kepmen": "Energi dan Infrastruktur Ramah Lingkungan",
        "sdg": [7, 13],  # #Ref E22 "Energi (infrastruktur ramah lingkungan)" → F22=(7), F23=(13)
        "keywords": ["energi terbarukan", "panel surya", "tenaga surya",
                     "energi surya", "pembangkit listrik", "efisiensi energi",
                     "hemat energi", "bangunan hijau", "green building",
                     "ramah lingkungan", "renewable energy", "solar panel",
                     "net zero", "karbon", "solar", "biodiesel", "biogas",
                     "green energy", "energi hijau", "transisi energi"],
        "indikator": "Jumlah/persentase infrastruktur energi ramah lingkungan PT",
        "formula": "sesuai ketentuan indikator energi pada Kepmen (infrastruktur "
                   "ramah lingkungan yang berfungsi pada tahun pelaporan)",
        "satuan": "Unit/%, cek dokumen resmi",
    },
    "limbah": {
        "dampak": "Lingkungan",
        "topik_kepmen": "Pengelolaan Limbah dan Daur Ulang",
        "sdg": [6, 12],  # #Ref E24 "Konsumsi bertanggung jawab (daur ulang/limbah)" → F24=(12), F25=(6)
        "keywords": ["limbah", "sampah", "daur ulang", "recycling", "bank sampah",
                     "kompos", "pengolahan limbah", "waste", "polusi",
                     "pencemaran", "tempat pengolahan sampah",
                     "plastic", "plastik", "microplastic", "waste management",
                     "pengelolaan sampah", "biodegradable"],
        "indikator": "Jumlah produk daur ulang dan/atau fasilitas pengolahan "
                     "limbah hasil kerja sama yang telah dimanfaatkan",
        "formula": "Jumlah seluruh produk daur ulang dan/atau fasilitas "
                   "pengolahan limbah yang telah dimanfaatkan pada tahun pelaporan",
        "satuan": "Produk atau fasilitas",
    },
    "transportasi": {
        "dampak": "Lingkungan",
        "topik_kepmen": "Mobilitas Ramah Lingkungan (Transportasi)",
        "sdg": [11, 13],  # #Ref E26 "Transportasi (jalur sepeda/pejalan kaki)" → F26=(11), F27=(13)
        "keywords": ["jalur sepeda", "pejalan kaki", "pedestrian", "sepeda",
                     "transportasi ramah", "mobilitas", "kampus hijau",
                     "bike", "jalan kaki", "bus kampus", "shuttle",
                     "bike lane", "trans jogja", "transportasi publik"],
        "indikator": "Ruas jalur sepeda dan jalur pejalan kaki di dalam area kampus",
        "formula": "Total panjang jalur sepeda + panjang jalur pejalan kaki",
        "satuan": "Kilometer (km) atau meter (m)",
    },
}

# ---- Gabungan semua tema (4 inti + 9 lengkap) ----
# Satu sumber kebenaran untuk dashboard & laporan: topik → pilar → SDG.
# sdg di-union dari TOPIK_KEPMEN (resmi, sheet Konten) dan TEMA_KEPMEN_LENGKAP.
TOPIK_KEPMEN_ALL = dict(TOPIK_KEPMEN)
TOPIK_KEPMEN_ALL.update(TEMA_KEPMEN_LENGKAP)

# Label tampilan per topik (ID berita_topik → nama pendek Indonesia).
LABEL_TOPIC_ALL = {
    "rehabilitasi_lingkungan": "Rehabilitasi Lingkungan",
    "kewirausahaan": "Kewirausahaan",
    "kunjungan_akademik": "Kunjungan Akademik",
    "kolaborasi_riset": "Kolaborasi Riset",
    "pendidikan_inklusif": "Pendidikan Inklusif",
    "penelitian_inovasi_sosial": "Penelitian & Inovasi Sosial",
    "pengabdian_masyarakat": "Pengabdian Masyarakat",
    "instansi_publik": "Kontribusi Instansi Publik",
    "pengajaran_pembelajaran": "Pengajaran & Pembelajaran",
    "belanja_umkm": "Belanja UMKM Lokal",
    "energi": "Energi & Infrastruktur",
    "limbah": "Limbah & Daur Ulang",
    "transportasi": "Mobilitas Ramah Lingkungan",
}

# Warna pilar (konsisten di semua chart).
WARNA_PILAR = {
    "Lingkungan": "#2e7d32",
    "Ekonomi": "#1565c0",
    "Sosial": "#e65100",
}
