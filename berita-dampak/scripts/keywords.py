"""Kamus kata kunci untuk klasifikasi berita dampak UGM.

SEMUA keyword bersumber dari detailing indikator tiap tema pada tabel Kepmen
361/M/KEP/2025 (bagian "DEFINISI, KRITERIA, KETENTUAN, DAN FORMULA", lihat
docs/kepmen_361_ocr.txt) — nama tema, definisi, kriteria, dan ketentuan.
Istilah yang tidak muncul di detailing tabel TIDAK dipakai sebagai keyword.
"""

KEYWORDS = {
    "rehabilitasi_lingkungan": [  # tema 13 Keanekaragaman Hayati
        # detailing: penanaman pohon/reboisasi, lahan kritis, restorasi hutan/
        # mangrove/sungai/danau/pesisir, pemulihan kualitas tanah-air-udara,
        # konservasi keanekaragaman hayati, pengendalian erosi/banjir, RTH
        "rehabilitasi lingkungan",
        "rehabilitasi lahan",
        "konservasi",
        "restorasi",
        "reboisasi",
        "lahan kritis",
        "ruang terbuka hijau",
        "erosi",
        "banjir",
        "hutan",
        "kehutanan",
        "forest",
        "forestry",
        "mangrove",
        "biodiversitas",
        "keanekaragaman hayati",
        "tree planting",
        "penanaman pohon",
    ],
    "kewirausahaan": [  # tema 7 Ekosistem Kewirausahaan
        # detailing: entitas spin-off/start-up, program inkubasi/kewirausahaan/
        # pengembangan bisnis PT, inkubator bisnis, NIB/akta pendirian
        "kewirausahaan",
        "wirausaha",
        "startup",
        "start-up",
        "start up",
        "entrepreneur",
        "entrepreneurship",
        "inkubasi bisnis",
        "inkubator bisnis",
        "inkubator",
        "spin-off",
        "spin off",
    ],
    "kunjungan_akademik": [  # tema 8 Kunjungan Akademik & Pengeluaran Pengunjung
        # detailing: academic event tourism, wisuda, seminar, konferensi/
        # simposium, lomba, festival, kegiatan mahasiswa, kunjungan akademik,
        # gathering alumni
        "kunjungan akademik",
        "wisuda",
        "seminar",
        "konferensi",
        "simposium",
        "lomba",
        "festival",
        "gathering alumni",
        "academic event",
        "academic visit",
    ],
    "kolaborasi_riset": [  # tema 6 Penelitian & Pertukaran Pengetahuan
        # detailing: pendapatan PT dari hilirisasi/komersialisasi/lisensi/
        # penjualan/kerja sama atas hasil riset, paten, prototipe, teknologi,
        # spin-off dengan industri, pemerintah, atau mitra; royalti, HKI
        "kolaborasi riset",
        "kerja sama penelitian",
        "riset bersama",
        "research collaboration",
        "joint research",
        "kerjasama riset",
        "kerja sama riset",
        "kerjasama penelitian",
        "penelitian bersama",
        "hilirisasi",
        "hilirisasi riset",
        "paten",
        "lisensi",
        "royalti",
        "komersialisasi",
        "hki",
        "hak kekayaan intelektual",
        "prototipe",
        "spin-off",
        "spin off",
    ],
}
