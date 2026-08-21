"""Pemetaan topik dampak → 14 Tema Resmi Kepmen 361/M/KEP/2025 → Klaster SDGs.

Sumber:
- UGM Analytics.xlsx sheet "Konten UGM Berdampak" (7 baris resmi) + "#Ref"
  (Dampak → Topik Resmi Kepmen → Daftar SDGs).
- Salinan_Kepmen_361_M_KEP_2025_Indikator_Dampak.pdf (OCR:
  docs/kepmen_361_ocr.txt) — definisi & kriteria indikator resmi.

14 tema resmi (3 pilar):
- Sosial (4): Pendidikan Inklusif, Penelitian dan Inovasi, Pengabdian dan
  Pengembangan Masyarakat, Kebijakan Publik.
- Ekonomi (5): Pengajaran dan Pembelajaran, Penelitian dan Pertukaran
  Pengetahuan, Ekosistem Kewirausahaan, Kunjungan Akademik dan Pengeluaran
  Pengunjung, Pengeluaran Institusi.
- Lingkungan (5): Energi, Transportasi, Konsumsi yang Bertanggung Jawab,
  Keanekaragaman Hayati, Pendidikan dan Penelitian.

Dipakai oleh tag_kepmen_all.py (tagging berita), dashboard, dan laporan
statis. Key topik (contoh 'limbah') adalah id internal; 'topik_kepmen' adalah
nama resmi tema.
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

# ---- 4 topik inti berita (TOPIK_KEPMEN) — pemetaan resmi dari xlsx ----
# 'dampak' = pilar, 'topik_kepmen' = nama resmi tema, 'sdg' = klaster SDGs.
# 'definisi'/'kriteria'/'formula'/'satuan' dari PDF Kepmen 361 (OCR).
TOPIK_KEPMEN = {
    "rehabilitasi_lingkungan": {
        "dampak": "Lingkungan",
        "topik_kepmen": "Keanekaragaman Hayati",
        "sdg": [13, 14, 15],
        "indikator": "Jumlah program rehabilitasi dan restorasi lingkungan Perguruan Tinggi",
        "definisi": "Jumlah program rehabilitasi dan restorasi lingkungan yang "
                    "dilaksanakan oleh perguruan tinggi pada periode berjalan.",
        "kriteria": "Program penanaman pohon, reboisasi, rehabilitasi lahan "
                    "kritis, restorasi hutan/mangrove/sungai/pesisir, pemulihan "
                    "kualitas tanah-air-udara, konservasi kehati, pengendalian "
                    "erosi/banjir, ruang terbuka hijau, dll. Satu program "
                    "dihitung 1 (satu) kali; bukti laporan kegiatan.",
        "formula": "Jumlah program rehabilitasi dan restorasi lingkungan yang "
                   "dilaksanakan pada periode berjalan.",
        "satuan": "Program",
    },
    "kewirausahaan": {
        "dampak": "Ekonomi",
        "topik_kepmen": "Ekosistem Kewirausahaan",
        "sdg": [8, 9],
        "indikator": "Jumlah entitas spin-off atau start-up dari Perguruan Tinggi yang masih aktif",
        "definisi": "Jumlah perusahaan, unit usaha, atau entitas bisnis "
                    "(spin-off/start-up) yang dibentuk berdasarkan hasil riset, "
                    "inovasi, teknologi, atau proses inkubasi perguruan tinggi "
                    "dan masih aktif beroperasi pada tahun pelaporan.",
        "kriteria": "Entitas didirikan oleh dosen/mahasiswa/alumni/tendik dengan "
                    "memanfaatkan hasil riset PT, atau memperoleh pendampingan/"
                    "inkubasi/fasilitasi PT, atau memakai HKI/teknologi PT; "
                    "masih aktif (NIB/akta, laporan usaha, bukti transaksi). "
                    "Entitas non-aktif atau masih perencanaan tidak dihitung.",
        "formula": "Jumlah entitas spin-off/start-up PT yang masih aktif dalam "
                   "periode berjalan.",
        "satuan": "Entitas",
    },
    "kunjungan_akademik": {
        "dampak": "Ekonomi",
        "topik_kepmen": "Kunjungan Akademik dan Pengeluaran Pengunjung",
        "sdg": [8, 11],
        "indikator": "Jumlah pengeluaran pengunjung kegiatan akademik",
        "definisi": "Jumlah pengeluaran pengunjung kegiatan akademik perguruan "
                    "tinggi (wisuda, seminar/konferensi, lomba/festival, "
                    "kunjungan akademik, gathering alumni) pada tahun pelaporan.",
        "kriteria": "Rata-rata pengeluaran per pengunjung (Rp) × jumlah "
                    "pengunjung; belanja akomodasi, makanan, transportasi, "
                    "atraksi, retail.",
        "formula": "Rata-rata pengeluaran per pengunjung (Rp) x Jumlah "
                   "Pengunjung Kegiatan Akademik.",
        "satuan": "Rupiah (Rp)",
    },
    "kolaborasi_riset": {
        "dampak": "Ekonomi",
        "topik_kepmen": "Penelitian dan Pertukaran Pengetahuan",
        "sdg": [9, 17],
        "indikator": "Jumlah pendapatan yang diterima Perguruan Tinggi dari "
                     "hilirisasi hasil riset dan/atau spin-off dengan industri "
                     "dan pemerintah",
        "definisi": "Jumlah pendapatan yang diterima perguruan tinggi dari "
                    "pemanfaatan, komersialisasi, lisensi, penjualan, atau "
                    "kerja sama atas hasil riset, paten, prototipe, teknologi, "
                    "dan/atau spin-off dengan industri, pemerintah, atau mitra "
                    "lainnya pada tahun pelaporan.",
        "kriteria": "Pendapatan dari lisensi paten/hak cipta/HKI, royalti, "
                    "penjualan prototipe/produk/teknologi, kerja sama "
                    "pemanfaatan hasil riset, pendapatan unit usaha/spin-off; "
                    "hanya pendapatan terealisasi yang tercatat di laporan "
                    "keuangan dan terbukti dengan dokumen resmi.",
        "formula": "Jumlah pendapatan dari hilirisasi riset / paten / prototipe "
                   "/ HKI / spin-off pada periode berjalan.",
        "satuan": "Rupiah (Rp)",
    },
}


def sdg_label(sdg: int) -> str:
    """Label ringkas: 'SDG 13 — Penanganan Perubahan Iklim'."""
    return f"SDG {sdg} — {SDG_NAMA[sdg]}"


# ---- 14 tema resmi Kepmen 361/M/KEP/2025 (semua pilar) ----
# 4 topik inti (TOPIK_KEPMEN di atas) adalah subset. Keyword dipakai untuk
# menandai berita yang ADA di tabel berita — bukan untuk fetch baru.
# sdg: klaster SDGs dari sheet "#Ref" (satu topik bisa berlanjut ke beberapa
# baris F di bawahnya).
TEMA_KEPMEN_LENGKAP = {
    # ---- Dampak Sosial (4 tema) ----
    "pendidikan_inklusif": {
        "dampak": "Sosial",
        "topik_kepmen": "Pendidikan Inklusif",
        "sdg": [1, 4, 10],  # #Ref E3 (F3=(4), F4=(10), F5=(1)); Konten D7=(1),(4),(10)
        "keywords": ["pendidikan inklusif", "pendidikan inklusi", "inklusi",
                     "afirmasi", "disabilitas", "difabel", "penyandang disabilitas",
                     "daerah tertinggal", "daerah terdepan", "daerah terluar",
                     "daerah 3t", "kip kuliah", "beasiswa afirmasi",
                     "beasiswa internal", "kelompok afirmasi",
                     "inclusive education"],
        "indikator": "Persentase lulusan/mahasiswa kelompok afirmasi yang "
                     "terserap kerja/wirausaha/studi lanjut atau penerima beasiswa internal",
        "definisi": "Persentase lulusan kelompok afirmasi (ekonomi tidak mampu, "
                    "penyandang disabilitas, daerah 3T) yang memperoleh "
                    "pekerjaan, berwirausaha, atau melanjutkan studi paling "
                    "lama 1 tahun setelah lulus; serta persentase mahasiswa "
                    "afirmasi penerima beasiswa internal PT.",
        "kriteria": "Lulusan afirmasi: penerima KIP Kuliah/UKT 1-2/bantuan "
                    "serupa, SKTM, penghasilan orang tua di bawah UMP; "
                    "penyandang disabilitas; berasal dari daerah 3T. Bekerja "
                    "di BUMN/lembaga internasional/non-profit, wirausaha ≥12 "
                    "bulan, magang berbayar, atau studi lanjut; data tracer study.",
        "formula": "Total lulusan kelompok afirmasi yang bekerja/wirausaha/studi "
                   "lanjut dibagi total lulusan kelompok afirmasi × 100%",
        "satuan": "% (Persentase)",
    },
    "penelitian_inovasi_sosial": {
        "dampak": "Sosial",
        "topik_kepmen": "Penelitian dan Inovasi",
        "sdg": [1, 9],  # #Ref E6 → F6=(9), F7=(1)
        "keywords": ["hasil riset", "pemanfaatan riset", "masyarakat rentan",
                     "teknologi tepat guna", "inovasi", "riset inovasi",
                     "rekomendasi kebijakan", "prototipe", "wilayah prioritas"],
        "indikator": "Persentase hasil riset perguruan tinggi yang dimanfaatkan "
                     "oleh masyarakat rentan dan/atau wilayah prioritas pembangunan",
        "definisi": "Persentase hasil riset, inovasi, teknologi, model, metode, "
                    "atau rekomendasi kebijakan perguruan tinggi yang telah "
                    "dimanfaatkan secara nyata oleh kelompok masyarakat rentan "
                    "dan/atau wilayah prioritas pembangunan pada periode pelaporan.",
        "kriteria": "Hasil riset: teknologi tepat guna, produk/prototipe, model "
                    "pemberdayaan, metode/prosedur, aplikasi/sistem digital, "
                    "rekomendasi kebijakan, bahan ajar/modul/pelatihan. "
                    "Dimanfaatkan bila digunakan langsung, diterapkan di "
                    "program pemerintah/desa/sekolah/puskesmas/UMKM, diadopsi "
                    "jadi pedoman, dipakai pelatihan/pendampingan, atau "
                    "berkelanjutan ≥3 bulan; ada bukti (surat keterangan, "
                    "berita acara, laporan implementasi).",
        "formula": "Jumlah hasil riset yang dimanfaatkan ÷ total hasil riset "
                   "pada periode berjalan × 100%",
        "satuan": "% (Persentase)",
    },
    "pengabdian_masyarakat": {
        "dampak": "Sosial",
        "topik_kepmen": "Pengabdian dan Pengembangan Masyarakat",
        "sdg": [1, 8, 11, 17],  # #Ref E8 (8,1,11) + E9 desa binaan (1,11) + Konten D5 (1,11,17)
        "keywords": ["pengabdian", "pengembangan masyarakat", "kuliah kerja nyata",
                     "kkn", "desa binaan", "pemberdayaan", "penyuluhan",
                     "pendampingan", "produk inovasi", "umkm", "bumdes",
                     "digitalisasi desa", "ketahanan pangan",
                     "community service", "community empowerment",
                     "pengabdian masyarakat", "pemberdayaan masyarakat"],
        "indikator": "Jumlah produk inovasi PT yang digunakan oleh UMKM lokal; "
                     "total dana pengabdian masyarakat; jumlah desa binaan aktif",
        "definisi": "Jumlah produk inovasi perguruan tinggi yang digunakan oleh "
                    "UMKM lokal, total dana yang disalurkan untuk program "
                    "pengabdian dan pengembangan masyarakat, dan jumlah desa "
                    "binaan aktif pada periode pelaporan.",
        "kriteria": "Produk inovasi: teknologi tepat guna, alat/mesin, "
                    "aplikasi, metode produksi, desain, model bisnis, SOP, "
                    "formula/resep; digunakan ≥3 bulan atau ada "
                    "pelatihan/pendampingan. Dana: program pemberdayaan, "
                    "pendampingan desa, pelatihan/penyuluhan, pengembangan "
                    "UMKM; realisasi tercatat laporan keuangan. Desa binaan: "
                    "MoU/MoA/PKS berlaku + minimal 1 program tahun berjalan.",
        "formula": "Jumlah seluruh produk inovasi yang digunakan UMKM lokal "
                   "pada periode berjalan (satuan: Produk)",
        "satuan": "Produk",
    },
    "instansi_publik": {
        "dampak": "Sosial",
        "topik_kepmen": "Kebijakan Publik",
        "sdg": [16, 17],  # #Ref E11 "Kebijakan publik (pendampingan instansi)" → F11=(16), F12=(17)
        "keywords": ["pendampingan instansi", "instansi publik", "pemerintah daerah",
                     "kebijakan publik", "tata kelola", "perangkat daerah",
                     "asistensi", "pemda", "local government",
                     "pemerintah kabupaten", "pemerintah provinsi",
                     "kementerian", "puskesmas", "pemerintah desa",
                     "kelurahan"],
        "indikator": "Jumlah instansi publik yang menerima pendampingan dari PT",
        "definisi": "Jumlah instansi publik yang menerima pendampingan dari "
                    "perguruan tinggi dalam rangka peningkatan tata kelola, "
                    "pelayanan, kapasitas kelembagaan, atau pelaksanaan "
                    "program pada tahun pelaporan.",
        "kriteria": "Instansi: pemerintah daerah/perangkat daerah, pemerintah "
                    "desa/kelurahan, unit layanan publik (sekolah, puskesmas, "
                    "RSUD). Pendampingan: pelatihan, asistensi/konsultasi, "
                    "penyusunan SOP/pedoman, pendampingan program, fasilitasi "
                    "dokumen/perencanaan/evaluasi. Insidental/seremonial/"
                    "kunjungan tanpa tindak lanjut tidak dihitung; ada bukti "
                    "(dokumen kerja sama, surat tugas, laporan).",
        "formula": "Jumlah instansi publik yang menerima pendampingan pada "
                   "periode berjalan",
        "satuan": "Instansi publik",
    },
    # ---- Dampak Ekonomi (5 tema) ----
    "pengajaran_pembelajaran": {
        "dampak": "Ekonomi",
        "topik_kepmen": "Pengajaran dan Pembelajaran",
        "sdg": [8],  # #Ref E13 → F13=(8)
        "keywords": ["pengeluaran mahasiswa", "biaya hidup mahasiswa",
                     "konsumsi mahasiswa", "transportasi mahasiswa",
                     "belanja mahasiswa", "student spending",
                     "cost of living"],
        "indikator": "Jumlah pengeluaran mahasiswa terkait transportasi dan konsumsi harian",
        "definisi": "Total nilai pengeluaran mahasiswa yang digunakan untuk "
                    "transportasi dan konsumsi harian selama menempuh "
                    "pendidikan pada tahun pelaporan.",
        "kriteria": "Transportasi: angkutan umum, ojek/transportasi daring, "
                    "bahan bakar, parkir, perjalanan harian. Konsumsi: "
                    "makanan/minuman, bahan pokok, kantin, warung, rumah "
                    "makan. Rata-rata per mahasiswa per bulan × jumlah "
                    "mahasiswa aktif × 12. Biaya kuliah/tinggal/hiburan/"
                    "elektronik tidak dihitung; data survei/kuesioner.",
        "formula": "Rata-rata pengeluaran per mahasiswa per bulan × jumlah "
                   "mahasiswa aktif × 12",
        "satuan": "Rupiah (Rp)",
    },
    "belanja_umkm": {
        "dampak": "Ekonomi",
        "topik_kepmen": "Pengeluaran Institusi",
        "sdg": [8, 12],  # #Ref E20 → F20=(8), F21=(12)
        "keywords": ["umkm lokal", "belanja umkm", "katering", "pengadaan barang",
                     "produk lokal", "usaha mikro", "usaha kecil", "pengadaan jasa",
                     "pembelian produk umkm", "local product", "suvenir",
                     "smes"],
        "indikator": "Jumlah belanja yang dikeluarkan PT untuk UMKM lokal",
        "definisi": "Jumlah nilai belanja atau pengeluaran perguruan tinggi "
                    "untuk pengadaan barang dan jasa kepada UMKM lokal.",
        "kriteria": "Belanja katering, pengadaan barang, suvenir, dan pengadaan "
                    "jasa dari UMKM lokal (usaha mikro/kecil/menengah yang "
                    "berlokasi di sekitar PT atau mitra program PT); tercatat "
                    "dalam laporan keuangan tahun pelaporan.",
        "formula": "Jumlah nilai belanja pengadaan barang/jasa kepada UMKM "
                   "lokal pada tahun pelaporan",
        "satuan": "Rupiah (Rp)",
    },
    # ---- Dampak Lingkungan (5 tema) ----
    "energi": {
        "dampak": "Lingkungan",
        "topik_kepmen": "Energi",
        "sdg": [7, 13],  # #Ref E22 → F22=(7), F23=(13)
        "keywords": ["energi terbarukan", "panel surya", "tenaga surya",
                     "energi surya", "pembangkit listrik", "efisiensi energi",
                     "hemat energi", "ramah lingkungan", "renewable energy",
                     "solar panel", "solar", "biogas", "green energy",
                     "energi hijau", "emisi", "plts", "mikrohidro",
                     "kendaraan listrik"],
        "indikator": "Jumlah infrastruktur ramah lingkungan hasil kolaborasi PT",
        "definisi": "Jumlah infrastruktur ramah lingkungan yang dibangun, "
                    "dikembangkan, atau diterapkan melalui kolaborasi "
                    "perguruan tinggi dengan pihak eksternal dan telah "
                    "dimanfaatkan secara nyata pada tahun pelaporan.",
        "kriteria": "Infrastruktur: PLTS, PLTMH, instalasi biogas, SPKLU, "
                    "lampu hemat energi/tenaga surya, sistem pengelolaan "
                    "energi bangunan, fasilitas pengolahan limbah menjadi "
                    "energi. Kolaborasi dengan masyarakat/pemerintah/industri/"
                    "sekolah/lembaga donor; selesai, berfungsi, dimanfaatkan "
                    "nyata; bukti berita acara/dokumentasi/laporan/MoU.",
        "formula": "Jumlah seluruh infrastruktur ramah lingkungan hasil "
                   "kolaborasi PT dengan pihak eksternal yang telah "
                   "dimanfaatkan pada tahun pelaporan",
        "satuan": "Infrastruktur",
    },
    "limbah": {
        "dampak": "Lingkungan",
        "topik_kepmen": "Konsumsi yang Bertanggung Jawab",
        "sdg": [6, 12],  # #Ref E24 → F24=(12), F25=(6)
        "keywords": ["limbah", "sampah", "daur ulang", "recycling", "bank sampah",
                     "kompos", "pupuk organik", "pengolahan limbah", "waste",
                     "tempat pengolahan sampah", "plastic", "plastik",
                     "waste management", "pengelolaan sampah",
                     "ekonomi sirkular", "ipal", "komposting"],
        "indikator": "Jumlah produk daur ulang dan/atau fasilitas pengolahan "
                     "limbah hasil kerja sama yang telah dimanfaatkan",
        "definisi": "Jumlah produk daur ulang dan/atau fasilitas pengolahan "
                    "limbah yang dihasilkan, dibangun, dikembangkan, atau "
                    "diterapkan melalui kerja sama perguruan tinggi dengan "
                    "pemerintah, industri, dan/atau masyarakat pada tahun "
                    "pelaporan.",
        "kriteria": "Produk daur ulang: olahan sampah plastik, kompos/pupuk "
                    "organik, bahan bangunan dari limbah, kerajinan dari "
                    "limbah, bahan bakar alternatif dari limbah. Fasilitas: "
                    "bank sampah, IPAL, TPS terpadu, fasilitas komposting, "
                    "fasilitas limbah-ke-energi, mesin pencacah/pemilah. "
                    "Selesai, berfungsi, dimanfaatkan nyata tahun pelaporan; "
                    "ada kerja sama eksternal.",
        "formula": "Jumlah seluruh produk daur ulang dan/atau fasilitas "
                   "pengolahan limbah yang telah dimanfaatkan pada tahun pelaporan",
        "satuan": "Produk atau fasilitas",
    },
    "transportasi": {
        "dampak": "Lingkungan",
        "topik_kepmen": "Transportasi",
        "sdg": [11, 13],  # #Ref E26 → F26=(11), F27=(13)
        "keywords": ["jalur sepeda", "pejalan kaki", "pedestrian", "sepeda",
                     "mobilitas", "bike", "jalan kaki", "bike lane"],
        "indikator": "Ruas jalur sepeda dan jalur pejalan kaki di dalam area kampus",
        "definisi": "Total panjang jalur sepeda dan jalur pejalan kaki yang "
                    "tersedia dan dapat digunakan di dalam area kampus pada "
                    "tahun pelaporan.",
        "kriteria": "Jalur sepeda khusus, pedestrian, jalur campuran "
                    "bermarka/berpembatas, konektivitas antar gedung/fakultas/"
                    "asrama/ruang terbuka; berada di area kampus, tersedia & "
                    "dapat digunakan, ada marka/pembatas/trotoar; rusak "
                    "berat/belum selesai tidak dihitung; tidak dihitung ganda.",
        "formula": "Total panjang jalur sepeda + panjang jalur pejalan kaki",
        "satuan": "Kilometer (km) atau meter (m)",
    },
    "pendidikan_dan_penelitian": {
        "dampak": "Lingkungan",
        "topik_kepmen": "Pendidikan dan Penelitian",
        "sdg": [14, 15],  # #Ref E37 "Kehati (mata kuliah)" (15,14) + E39 "Rehabilitasi & restorasi (mata kuliah)" (15,14)
        "keywords": ["mata kuliah", "modul pembelajaran", "kurikulum sustainability",
                     "kurikulum berkelanjutan", "pembelajaran berkelanjutan",
                     "education for sustainable development", "esd",
                     "sustainable education", "biodiversitas dalam pembelajaran",
                     "keberlanjutan dalam pembelajaran"],
        "indikator": "Jumlah mata kuliah dan/atau modul pembelajaran yang "
                     "memuat materi sustainability dan biodiversitas",
        "definisi": "Jumlah mata kuliah dan/atau modul pembelajaran yang "
                    "memuat materi tentang keberlanjutan (sustainability) dan "
                    "biodiversitas yang diselenggarakan oleh perguruan tinggi "
                    "pada tahun akademik berjalan.",
        "kriteria": "Materi: pembangunan berkelanjutan, perubahan iklim, energi "
                    "terbarukan, pengelolaan limbah, ekonomi sirkular, "
                    "konservasi lingkungan, keanekaragaman hayati, rehabilitasi/"
                    "restorasi lingkungan, pengelolaan SDA. Mata kuliah "
                    "wajib/pilihan/lintas prodi/umum; modul mandiri/pelatihan/"
                    "short course; tercantum kurikulum/RPS, diselenggarakan "
                    "tahun berjalan, memuat ≥1 topik secara substansial; yang "
                    "hanya menyinggung sepintas tidak dihitung.",
        "formula": "Jumlah mata kuliah + modul yang memuat materi "
                   "sustainability/biodiversitas pada tahun akademik berjalan",
        "satuan": "Mata kuliah/modul",
    },
}

# ---- Gabungan semua tema (4 inti + 10 lengkap = 14 tema resmi) ----
# Satu sumber kebenaran untuk dashboard & laporan: topik → pilar → SDG.
# sdg di-union dari TOPIK_KEPMEN (resmi, sheet Konten) dan TEMA_KEPMEN_LENGKAP.
TOPIK_KEPMEN_ALL = dict(TOPIK_KEPMEN)
TOPIK_KEPMEN_ALL.update(TEMA_KEPMEN_LENGKAP)

# Label tampilan per topik (id internal → nama pendek Indonesia).
LABEL_TOPIC_ALL = {
    "rehabilitasi_lingkungan": "Keanekaragaman Hayati",
    "kewirausahaan": "Kewirausahaan",
    "kunjungan_akademik": "Kunjungan Akademik",
    "kolaborasi_riset": "Kolaborasi Riset",
    "pendidikan_inklusif": "Pendidikan Inklusif",
    "penelitian_inovasi_sosial": "Penelitian & Inovasi",
    "pengabdian_masyarakat": "Pengabdian Masyarakat",
    "instansi_publik": "Kebijakan Publik",
    "pengajaran_pembelajaran": "Pengajaran & Pembelajaran",
    "belanja_umkm": "Pengeluaran Institusi",
    "energi": "Energi",
    "limbah": "Konsumsi yang Bertanggung Jawab",
    "transportasi": "Transportasi",
    "pendidikan_dan_penelitian": "Pendidikan & Penelitian",
}

# Warna pilar (konsisten di semua chart).
WARNA_PILAR = {
    "Lingkungan": "#2e7d32",
    "Ekonomi": "#1565c0",
    "Sosial": "#e65100",
}
