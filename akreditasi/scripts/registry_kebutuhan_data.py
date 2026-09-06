"""Registry kebutuhan data LED & LKPS -- SATU SUMBER KEBENARAN.

Sumber: docs/Data_Requirements_LED_LKPS_MEI.md (hasil review LED + LKPS
Prodi Magister Elektronika dan Instrumentasi/MEI, instrumen LAM-INFOKOM).
Pola modul ini meniru berita-dampak/scripts/kepmen_sdg.py: dict of dicts,
di-*import* langsung oleh dashboard & generator dokumen -- tidak ada
sumber lain yang perlu disinkronkan manual.

Cakupan v1 -- keputusan scoping (baca sebelum menambah/mengubah item):

1. **Item "tabel"** (28 item) = 1:1 dengan tabel-tabel LKPS Bagian 1-6 di
   dokumen sumber. `kolom_dibutuhkan` diambil literal dari kolom yang
   disebut di deskripsi tiap tabel. Dokumen menyebut "LKPS berisi 26 tabel"
   tapi listing per-Bagian di dokumen yang sama punya 28 baris (mis. 2.B.4
   dan 2.B.4.1 dihitung terpisah) -- inkonsistensi kecil di dokumen sumber,
   BUKAN dirapikan di sini; kita ikuti listing literal (28 item), bukan
   angka ringkasannya.
2. **`kriteria_led` untuk item tabel** di-map ke kriteria LED terdekat
   berdasar ISI tabelnya (dokumen sumber TIDAK punya crosswalk eksplisit
   tabel<->kriteria) -- Bagian 2 Pendidikan -> semua C2, Bagian 3 Penelitian
   -> semua C3, Bagian 4 PkM -> semua C4; Bagian 1 & 5 (tata kelola/sarpras)
   dipecah ke B/C1/C2/C5 sesuai topik baris; Bagian 6 -> C6. Kalau assessor
   LAM-INFOKOM punya pemetaan resmi berbeda, cukup ubah field ini per item,
   struktur dashboard/generator otomatis ikut.
3. **Item "narasi"** = 18 item, mewakili Identitas & Administrasi (3),
   Kriteria A (1, digabung -- makro+mikro+SWOT tidak dipecah 14 sub-aspek),
   Kriteria B.1-B.8 (8), dan Kriteria C1-C6 (6). Untuk C1-C6, siklus PPEPP
   (Penetapan/Pelaksanaan/Evaluasi/Pengendalian/Peningkatan) DITARUH sebagai
   5 `kolom_dibutuhkan` dalam SATU item per kriteria -- bukan dipecah jadi
   30 item terpisah (6 kriteria x 5 tahap) -- supaya registry tetap ringkas
   (~49 item, bukan ~170). Kalau butuh tracking lebih granular per tahap
   PPEPP nanti, pecah item ini jadi 5 dulu, pola lain tidak perlu berubah.
4. **D1-D3** (kekhasan kurikulum) = 3 item "tabel", kriteria_led "D" --
   ini bagian LED (bukan LKPS), tapi datanya tabular (daftar mata kuliah)
   jadi dipakai tipe="tabel" seperti item LKPS.
5. **status_ketersediaan**: SEMUA item "belum_tersedia" atau
   "perlu_input_manual" (`mysql_table=None` untuk seluruh 49 item) --
   sesuai temuan dokumen sumber ("belum ada satu sistem tunggal yang
   mengagregasi data akreditasi"). Pemilihan salah satu dari dua status itu
   per item adalah judgment call: tabel/narasi kecil yang jelas bisa diisi
   tim penyusun dalam waktu dekat -> "perlu_input_manual"; yang butuh
   survei/tracer study/dokumen kebijakan yang belum ada -> "belum_tersedia".
   Sesuaikan manual per item begitu proses pengisian riil berjalan.
6. **Pemisahan dokumen LED vs LKPS** (dashboard/generator) DITURUNKAN dari
   `tabel_lkps`, bukan field baru: item ber-`tabel_lkps` "1.x".."6.x"/"6"
   (persis Bagian LKPS 1-6, lihat `_bagian_dari_tabel`) = dokumen "LKPS";
   sisanya (`tabel_lkps` None ATAU "D1"/"D2"/"D3") = dokumen "LED" --
   D1-D3 tetap LED walau tipe="tabel" (kekhasan kurikulum ada di LED, bukan
   Bagian LKPS manapun). Tiap tab Kriteria A/B/C1-C6 di mode LED menampilkan
   cuplikan read-only item LKPS ber-`kriteria_led` sama (evidence PPEPP) --
   form input TETAP hanya di sisi LKPS (satu item = satu tempat isi data),
   lihat `lkps_cuplikan_untuk_kriteria`.
"""

# Urutan tampilan kriteria di dashboard (tab) & dokumen (heading per Bab).
URUTAN_KRITERIA = ["Umum", "A", "B", "C1", "C2", "C3", "C4", "C5", "C6", "D"]

LABEL_KRITERIA = {
    "Umum": "Umum — Identitas & Administrasi",
    "A": "Kriteria A — Kondisi Eksternal",
    "B": "Kriteria B — Profil UPPS dan PS",
    "C1": "Kriteria C1 — Budaya Mutu",
    "C2": "Kriteria C2 — Relevansi Pendidikan",
    "C3": "Kriteria C3 — Penelitian",
    "C4": "Kriteria C4 — Relevansi PkM",
    "C5": "Kriteria C5 — Akuntabilitas",
    "C6": "Kriteria C6 — Diferensiasi Misi",
    "D": "Kriteria D — Suplemen Program Studi (Kekhasan Kurikulum)",
}

STATUS_LABEL = {
    "tersedia_otomatis": "🟢 Tersedia otomatis",
    "perlu_input_manual": "🟡 Perlu input manual",
    "belum_tersedia": "🔴 Belum tersedia",
}

URUTAN_BAGIAN_LKPS = ["1", "2", "3", "4", "5", "6"]

LABEL_BAGIAN_LKPS = {
    "1": "Bagian 1 — Tata Kelola",
    "2": "Bagian 2 — Pendidikan",
    "3": "Bagian 3 — Penelitian",
    "4": "Bagian 4 — PkM",
    "5": "Bagian 5 — Sistem Tata Kelola & Sarpras",
    "6": "Bagian 6 — Diferensiasi Misi",
}

_KOLOM_PPEPP = [
    "Dokumen Penetapan / Kebijakan (link)",
    "Bukti Pelaksanaan",
    "Evaluasi Capaian (TS-2/TS-1/TS)",
    "Rencana Tindak Lanjut (RTL)",
    "Hasil Peningkatan setelah RTL",
]

KEBUTUHAN_DATA: dict[str, dict] = {
    # ============== Umum — Identitas & Administrasi ==============
    "identitas_pt_upps_ps": {
        "kriteria_led": "Umum",
        "tabel_lkps": None,
        "nama": "Identitas PT/UPPS/PS",
        "deskripsi_singkat": "Nama, alamat, kontak, no. SK pendirian PT & pembukaan PS, tanggal, pejabat penandatangan.",
        "tipe": "narasi",
        "kolom_dibutuhkan": ["Nama & Alamat PT/UPPS/PS", "Kontak", "No. & Tanggal SK Pendirian PT",
                              "No. & Tanggal SK Pembukaan PS", "Pejabat Penandatangan"],
        "sumber_data": "Rektorat/Biro Hukum & Tata Laksana UGM (arsip PDF)",
        "status_ketersediaan": "perlu_input_manual",
        "mysql_table": None,
    },
    "status_akreditasi_seluruh_ps": {
        "kriteria_led": "Umum",
        "tabel_lkps": None,
        "nama": "Status Akreditasi Seluruh PS di UPPS",
        "deskripsi_singkat": "Jenis program, nama PS, status/peringkat, no & tanggal SK, tanggal kadaluarsa, jumlah mahasiswa aktif.",
        "tipe": "tabel",
        "kolom_dibutuhkan": ["Jenis Program", "Nama PS", "Status/Peringkat", "No. & Tanggal SK",
                              "Tanggal Kadaluarsa", "Jumlah Mahasiswa Aktif"],
        "sumber_data": "LAM-INFOKOM (SK akreditasi) + SIMASTER",
        "status_ketersediaan": "perlu_input_manual",
        "mysql_table": None,
    },
    "tim_penyusun_led": {
        "kriteria_led": "Umum",
        "tabel_lkps": None,
        "nama": "Tim Penyusun LED",
        "deskripsi_singkat": "Nama, jabatan dalam tim, tanggung jawab penyusunan tiap bab/kriteria.",
        "tipe": "tabel",
        "kolom_dibutuhkan": ["Nama", "Jabatan dalam Tim", "Tanggung Jawab Bab/Kriteria"],
        "sumber_data": "SK Tim Penyusun (arsip internal UPPS)",
        "status_ketersediaan": "perlu_input_manual",
        "mysql_table": None,
    },

    # ============== Kriteria A — Kondisi Eksternal ==============
    "led_kriteria_a": {
        "kriteria_led": "A",
        "tabel_lkps": None,
        "nama": "Analisis Lingkungan Eksternal (Makro, Mikro, Sintesis)",
        "deskripsi_singkat": "5 aspek makro (kebijakan/ekonomi/sosial/budaya/IPTEK) + 9 aspek mikro + sintesis peluang strategis.",
        "tipe": "narasi",
        "kolom_dibutuhkan": [
            "Lingkungan Makro — Kebijakan", "Lingkungan Makro — Ekonomi", "Lingkungan Makro — Sosial",
            "Lingkungan Makro — Budaya", "Lingkungan Makro — IPTEK",
            "Lingkungan Mikro (9 aspek: pesaing, pengguna lulusan, dst.)",
            "Sintesis SWOT / Peluang Strategis",
        ],
        "sumber_data": "Rujukan eksternal (BPS, APJII, WEF, ranking QS, dll.) + analisis internal tim penyusun",
        "status_ketersediaan": "belum_tersedia",
        "mysql_table": None,
    },

    # ============== Kriteria B — Profil UPPS dan PS ==============
    "led_b1_sejarah": {
        "kriteria_led": "B", "tabel_lkps": None, "nama": "B.1 Sejarah",
        "deskripsi_singkat": "Tanggal & SK pendirian UPPS, tanggal pendirian PS, capaian akreditasi terkini.",
        "tipe": "narasi",
        "kolom_dibutuhkan": ["Tanggal & SK Pendirian UPPS", "Tanggal Pendirian PS", "Capaian Akreditasi Terkini"],
        "sumber_data": "Arsip SK internal", "status_ketersediaan": "perlu_input_manual", "mysql_table": None,
    },
    "led_b2_vmts": {
        "kriteria_led": "B", "tabel_lkps": None, "nama": "B.2 VMTS & Tata Nilai",
        "deskripsi_singkat": "Visi/misi/tujuan strategis UPPS & PS, Renstra multi-tahun, Target Capaian Kinerja (TCK) tahunan.",
        "tipe": "narasi",
        "kolom_dibutuhkan": ["Visi/Misi/Tujuan Strategis UPPS", "Visi/Misi/Tujuan Strategis PS",
                              "Renstra Multi-Tahun (link)", "Target Capaian Kinerja (TCK) Tahunan"],
        "sumber_data": "Dokumen Renstra UPPS/PS", "status_ketersediaan": "perlu_input_manual", "mysql_table": None,
    },
    "led_b3_organisasi": {
        "kriteria_led": "B", "tabel_lkps": None, "nama": "B.3 Organisasi & Tata Kerja",
        "deskripsi_singkat": "SK SOTK, daftar unit/lab di bawah UPPS, struktur mutu (gugus jaminan mutu, komite kurikulum).",
        "tipe": "narasi",
        "kolom_dibutuhkan": ["SK SOTK (link)", "Daftar Unit/Lab di bawah UPPS",
                              "Struktur Gugus Jaminan Mutu", "Struktur Komite Kurikulum"],
        "sumber_data": "SK SOTK Fakultas", "status_ketersediaan": "perlu_input_manual", "mysql_table": None,
    },
    "led_b4_mahasiswa_lulusan": {
        "kriteria_led": "B", "tabel_lkps": None, "nama": "B.4 Mahasiswa & Lulusan",
        "deskripsi_singkat": "Jumlah mahasiswa aktif, rata-rata penerimaan/tahun, jumlah lulusan, profil karier, skema dukungan.",
        "tipe": "narasi",
        "kolom_dibutuhkan": ["Jumlah Mahasiswa Aktif", "Rata-rata Penerimaan/Tahun", "Jumlah Lulusan",
                              "Profil Karier Lulusan", "Skema Dukungan (Beasiswa/Dana Publikasi)"],
        "sumber_data": "SIMASTER modul Pendidikan + tracer study",
        "status_ketersediaan": "perlu_input_manual", "mysql_table": None,
    },
    "led_b5_dosen_tendik": {
        "kriteria_led": "B", "tabel_lkps": None, "nama": "B.5 Dosen & Tendik",
        "deskripsi_singkat": "Jumlah dosen (per Des. tahun berjalan), dokumen proyeksi kenaikan pangkat, jumlah tenaga kependidikan.",
        "tipe": "narasi",
        "kolom_dibutuhkan": ["Jumlah Dosen (per Des. TS)", "Dokumen Proyeksi Kenaikan Pangkat",
                              "Jumlah Tenaga Kependidikan"],
        "sumber_data": "STAFF SIMASTER (staff.simaster.ugm.ac.id)",
        "status_ketersediaan": "perlu_input_manual", "mysql_table": None,
    },
    "led_b6_keuangan_sarpras": {
        "kriteria_led": "B", "tabel_lkps": None, "nama": "B.6 Keuangan, Sarana Prasarana",
        "deskripsi_singkat": "Sumber pendanaan (pemerintah/UKT/eksternal), luas & jumlah ruang kelas, fasilitas khusus.",
        "tipe": "narasi",
        "kolom_dibutuhkan": ["Sumber Pendanaan (Pemerintah/UKT/Eksternal)", "Luas & Jumlah Ruang Kelas",
                              "Fasilitas Khusus (Lab, Alat Riset Besar)"],
        "sumber_data": "FINANCE SIMASTER + SIMASET", "status_ketersediaan": "perlu_input_manual", "mysql_table": None,
    },
    "led_b7_spmi": {
        "kriteria_led": "B", "tabel_lkps": None, "nama": "B.7 Sistem Penjaminan Mutu",
        "deskripsi_singkat": "Struktur SPMI (siapa mengawal tiap tahap PPEPP), jumlah IKU/IKT yang dimandatkan TCK.",
        "tipe": "narasi",
        "kolom_dibutuhkan": ["Struktur SPMI (Pengawal per Tahap PPEPP)", "Jumlah IKU/IKT yang Dimandatkan TCK"],
        "sumber_data": "Gugus Jaminan Mutu dan Akreditasi (GJMA)",
        "status_ketersediaan": "belum_tersedia", "mysql_table": None,
    },
    "led_b8_kinerja_ringkas": {
        "kriteria_led": "B", "tabel_lkps": None, "nama": "B.8 Kinerja UPPS/PS Ringkas",
        "deskripsi_singkat": "Highlight capaian tiap pilar Tridharma (pendidikan, penelitian, PkM).",
        "tipe": "narasi",
        "kolom_dibutuhkan": ["Highlight Capaian Pendidikan", "Highlight Capaian Penelitian", "Highlight Capaian PkM"],
        "sumber_data": "Kompilasi dari data Bagian 2-4 LKPS",
        "status_ketersediaan": "belum_tersedia", "mysql_table": None,
    },
    "lkps_1_a_1": {
        "kriteria_led": "B", "tabel_lkps": "1.A.1", "nama": "Pimpinan & Tupoksi",
        "deskripsi_singkat": "Unit kerja, nama ketua, periode jabatan, pendidikan terakhir, jabatan fungsional, tupoksi.",
        "tipe": "tabel",
        "kolom_dibutuhkan": ["Unit Kerja", "Nama Ketua", "Periode Jabatan", "Pendidikan Terakhir",
                              "Jabatan Fungsional", "Uraian Tugas Pokok & Fungsi"],
        "sumber_data": "Rekap manual departemen (SK penugasan) + STAFF SIMASTER",
        "status_ketersediaan": "perlu_input_manual", "mysql_table": None,
    },
    "lkps_1_a_2": {
        "kriteria_led": "B", "tabel_lkps": "1.A.2", "nama": "Sumber Pendanaan UPPS/PS",
        "deskripsi_singkat": "Kategori sumber dana (SPP/UKT, Yayasan, Pemerintah, dst.) x nominal per tahun + link bukti.",
        "tipe": "tabel",
        "kolom_dibutuhkan": ["Kategori Sumber Dana", "TS-2 (Rp juta)", "TS-1 (Rp juta)", "TS (Rp juta)", "Link Bukti"],
        "sumber_data": "FINANCE SIMASTER (finance.simaster.ugm.ac.id) + rekap manual Google Spreadsheet UPPS",
        "status_ketersediaan": "perlu_input_manual", "mysql_table": None,
    },
    "lkps_1_a_3": {
        "kriteria_led": "B", "tabel_lkps": "1.A.3", "nama": "Penggunaan Dana",
        "deskripsi_singkat": "Kategori penggunaan (Pendidikan, Penelitian, PkM, Investasi) x nominal per tahun + link bukti.",
        "tipe": "tabel",
        "kolom_dibutuhkan": ["Kategori Penggunaan", "TS-2 (Rp juta)", "TS-1 (Rp juta)", "TS (Rp juta)", "Link Bukti"],
        "sumber_data": "Realisasi anggaran Fakultas (FMIPA) + rekap manual Google Spreadsheet",
        "status_ketersediaan": "perlu_input_manual", "mysql_table": None,
    },
    "lkps_1_a_4": {
        "kriteria_led": "C2", "tabel_lkps": "1.A.4", "nama": "Beban DTPR (EWMP)",
        "deskripsi_singkat": "SKS pengajaran, penelitian, PkM, manajemen per dosen per semester pada TS.",
        "tipe": "tabel",
        "kolom_dibutuhkan": ["Nama DTPR", "SKS Pengajaran", "SKS Penelitian", "SKS PkM", "SKS Manajemen",
                              "Total EWMP", "Semester/TS"],
        "sumber_data": "BKD (Beban Kerja Dosen)",
        "status_ketersediaan": "perlu_input_manual", "mysql_table": None,
    },
    "lkps_1_a_5": {
        "kriteria_led": "B", "tabel_lkps": "1.A.5", "nama": "Kualifikasi Tendik",
        "deskripsi_singkat": "Jenis tenaga kependidikan x jumlah per jenjang pendidikan (S3-SMA) x unit kerja.",
        "tipe": "tabel",
        "kolom_dibutuhkan": ["Jenis Tenaga Kependidikan", "Unit Kerja", "S3", "S2", "S1", "D4/D3", "SMA", "Jumlah"],
        "sumber_data": "STAFF SIMASTER (staff.simaster.ugm.ac.id)",
        "status_ketersediaan": "perlu_input_manual", "mysql_table": None,
    },
    "lkps_1_b": {
        "kriteria_led": "C1", "tabel_lkps": "1.B", "nama": "Unit SPMI & SDM",
        "deskripsi_singkat": "Nama unit SPMI, dokumen SPMI berlaku, jumlah auditor mutu internal, frekuensi audit/monev, bukti.",
        "tipe": "tabel",
        "kolom_dibutuhkan": ["Nama Unit SPMI", "Dokumen SPMI Berlaku (link)", "Jumlah Auditor Bersertifikat",
                              "Jumlah Auditor Non-Sertifikat", "Frekuensi Audit/Monev per Tahun", "Link Laporan Audit"],
        "sumber_data": "SIMASTER EDPS + Gugus Jaminan Mutu dan Akreditasi (GJMA)",
        "status_ketersediaan": "belum_tersedia", "mysql_table": None,
    },
    "lkps_5_2": {
        "kriteria_led": "B", "tabel_lkps": "5.2", "nama": "Sarana Prasarana Pendidikan (UPPS)",
        "deskripsi_singkat": "Sama pola dengan 2.A.4 tapi cakupan level UPPS (ruang pertemuan/rapat, dll.).",
        "tipe": "tabel",
        "kolom_dibutuhkan": ["Nama Ruang/Fasilitas", "Daya Tampung", "Luas (m2)", "Status Kepemilikan",
                              "Status Lisensi Perangkat Lunak", "Daftar Perangkat", "Link Bukti"],
        "sumber_data": "SIMASET (simaset.simaster.ugm.ac.id) + pendataan mandiri UPPS",
        "status_ketersediaan": "perlu_input_manual", "mysql_table": None,
    },

    # ============== Kriteria C1 — Budaya Mutu ==============
    "led_c1_budaya_mutu": {
        "kriteria_led": "C1", "tabel_lkps": None, "nama": "C1 Budaya Mutu",
        "deskripsi_singkat": "Tata kelola administrasi akademik/keuangan/SDM/kerja sama & sarpras UPPS, fungsi SPMI Prodi.",
        "tipe": "narasi", "kolom_dibutuhkan": list(_KOLOM_PPEPP),
        "sumber_data": "SIMASTER EDPS + GJMA", "status_ketersediaan": "belum_tersedia", "mysql_table": None,
    },
    "lkps_5_1": {
        "kriteria_led": "C5", "tabel_lkps": "5.1", "nama": "Sistem Tata Kelola",
        "deskripsi_singkat": "Jenis tata kelola, nama sistem informasi yang dipakai, jenis akses, unit pengelola, link akses.",
        "tipe": "tabel",
        "kolom_dibutuhkan": ["Jenis Tata Kelola", "Nama Sistem Informasi", "Jenis Akses (Lokal/Internet)",
                              "Unit Pengelola", "Link Akses Sistem"],
        "sumber_data": "Dokumentasi internal UPPS + Direktorat Teknologi Informasi UGM",
        "status_ketersediaan": "perlu_input_manual", "mysql_table": None,
    },

    # ============== Kriteria C2 — Relevansi Pendidikan ==============
    "led_c2_relevansi_pendidikan": {
        "kriteria_led": "C2", "tabel_lkps": None, "nama": "C2 Relevansi Pendidikan",
        "deskripsi_singkat": "Sarpras pendidikan, DTPR, pembiayaan, penerimaan mahasiswa baru, kurikulum, fleksibilitas pembelajaran, dst.",
        "tipe": "narasi", "kolom_dibutuhkan": list(_KOLOM_PPEPP),
        "sumber_data": "Kompilasi data Bagian 2 LKPS", "status_ketersediaan": "belum_tersedia", "mysql_table": None,
    },
    "lkps_2_a_2": {
        "kriteria_led": "C2", "tabel_lkps": "2.A.2", "nama": "Keragaman Asal Mahasiswa",
        "deskripsi_singkat": "Jumlah mahasiswa baru per kategori asal (kota/kab sama, kota/kab lain, provinsi lain, negara lain, afirmasi).",
        "tipe": "tabel",
        "kolom_dibutuhkan": ["Kategori Asal Mahasiswa", "Jumlah TS-2", "Jumlah TS-1", "Jumlah TS"],
        "sumber_data": "PDDIKTI + SIMASTER modul Pendidikan",
        "status_ketersediaan": "perlu_input_manual", "mysql_table": None,
    },
    "lkps_2_a_4": {
        "kriteria_led": "C2", "tabel_lkps": "2.A.4", "nama": "Sarana Prasarana Pendidikan",
        "deskripsi_singkat": "Nama ruang/fasilitas, daya tampung, luas, kepemilikan, lisensi perangkat lunak, daftar perangkat.",
        "tipe": "tabel",
        "kolom_dibutuhkan": ["Nama Ruang/Fasilitas", "Daya Tampung", "Luas (m2)", "Status Kepemilikan",
                              "Status Lisensi Perangkat Lunak", "Daftar Perangkat", "Link Bukti"],
        "sumber_data": "SIMASET + pendataan mandiri departemen",
        "status_ketersediaan": "perlu_input_manual", "mysql_table": None,
    },
    "lkps_2_a_7": {
        "kriteria_led": "C2", "tabel_lkps": "2.A.7", "nama": "Fasilitas Disabilitas",
        "deskripsi_singkat": "Lokasi/gedung, lingkup ruangan yang tersedia, jenis akses fasilitas difabel.",
        "tipe": "tabel",
        "kolom_dibutuhkan": ["Lokasi/Gedung", "Lingkup Ruangan", "Jenis Akses Fasilitas Difabel"],
        "sumber_data": "Pendataan mandiri departemen",
        "status_ketersediaan": "belum_tersedia", "mysql_table": None,
    },
    "lkps_2_b_1": {
        "kriteria_led": "C2", "tabel_lkps": "2.B.1", "nama": "Isi Pembelajaran",
        "deskripsi_singkat": "Kode MK, nama MK, SKS, semester penawaran, pemetaan CPL, profil lulusan, domain KKNI — per mata kuliah.",
        "tipe": "tabel",
        "kolom_dibutuhkan": ["Kode MK", "Nama MK", "SKS", "Semester Penawaran", "Pemetaan CPL (1-5)",
                              "Pemetaan Profil Lulusan", "Domain KKNI"],
        "sumber_data": "Dokumen Kurikulum Prodi resmi (SK Kurikulum)",
        "status_ketersediaan": "perlu_input_manual", "mysql_table": None,
    },
    "lkps_2_b_3": {
        "kriteria_led": "C2", "tabel_lkps": "2.B.3", "nama": "Peta Pemenuhan CPL",
        "deskripsi_singkat": "Matriks CPL x CPMK x mata kuliah pengampu per semester.",
        "tipe": "tabel",
        "kolom_dibutuhkan": ["CPL", "CPMK", "Mata Kuliah Pengampu", "Semester"],
        "sumber_data": "Dokumen Kurikulum Prodi + ELOK",
        "status_ketersediaan": "belum_tersedia", "mysql_table": None,
    },
    "lkps_2_b_4_1": {
        "kriteria_led": "C2", "tabel_lkps": "2.B.4.1", "nama": "MK Soft/Hard Competence",
        "deskripsi_singkat": "Daftar MK, kategori dukungan kompetensi (soft/hard/integrasi), analisis kontribusinya.",
        "tipe": "tabel",
        "kolom_dibutuhkan": ["Kode MK", "Nama MK", "Kategori (Soft/Hard/Integrasi)", "Analisis Kontribusi Kompetensi"],
        "sumber_data": "Dokumen Kurikulum Prodi",
        "status_ketersediaan": "belum_tersedia", "mysql_table": None,
    },
    "lkps_2_b_4": {
        "kriteria_led": "C2", "tabel_lkps": "2.B.4", "nama": "Masa Tunggu Kerja Lulusan",
        "deskripsi_singkat": "Tahun lulus, jumlah lulusan, jumlah lulusan terlacak, rata-rata waktu tunggu kerja pertama.",
        "tipe": "tabel",
        "kolom_dibutuhkan": ["Tahun Lulus", "Jumlah Lulusan", "Jumlah Lulusan Terlacak",
                              "Rata-rata Waktu Tunggu Kerja (bulan)"],
        "sumber_data": "Tracer study mandiri UPPS/Fakultas",
        "status_ketersediaan": "belum_tersedia", "mysql_table": None,
    },
    "lkps_2_b_5": {
        "kriteria_led": "C2", "tabel_lkps": "2.B.5", "nama": "Kesesuaian Bidang Kerja",
        "deskripsi_singkat": "Tahun lulus, jumlah lulusan terlacak, profesi sesuai/tidak sesuai bidang Infokom, lingkup tempat kerja.",
        "tipe": "tabel",
        "kolom_dibutuhkan": ["Tahun Lulus", "Jumlah Lulusan Terlacak", "Sesuai Bidang Infokom", "Tidak Sesuai",
                              "Lingkup Tempat Kerja (Lokal/Multinasional)"],
        "sumber_data": "Tracer study mandiri UPPS/Fakultas",
        "status_ketersediaan": "belum_tersedia", "mysql_table": None,
    },
    "lkps_2_b_6": {
        "kriteria_led": "C2", "tabel_lkps": "2.B.6", "nama": "Kepuasan Pengguna Lulusan",
        "deskripsi_singkat": "Jenis kemampuan dinilai, persentase tingkat kepuasan dari survei pengguna lulusan, RTL.",
        "tipe": "tabel",
        "kolom_dibutuhkan": ["Jenis Kemampuan Dinilai", "% Sangat Baik", "% Baik", "% Cukup", "% Kurang",
                              "Rencana Tindak Lanjut UPPS/PS"],
        "sumber_data": "Survei/kuesioner kepuasan pengguna lulusan",
        "status_ketersediaan": "belum_tersedia", "mysql_table": None,
    },
    "lkps_2_c": {
        "kriteria_led": "C2", "tabel_lkps": "2.C", "nama": "Fleksibilitas Pembelajaran",
        "deskripsi_singkat": "Jumlah mahasiswa aktif per tahun akademik; jumlah mahasiswa per bentuk pembelajaran.",
        "tipe": "tabel",
        "kolom_dibutuhkan": ["Tahun Akademik", "Jumlah Mahasiswa Aktif", "Micro-credential", "RPL",
                              "CBL/PBL", "Blended Learning"],
        "sumber_data": "SIMASTER modul Pendidikan / ELOK",
        "status_ketersediaan": "perlu_input_manual", "mysql_table": None,
    },
    "lkps_2_d": {
        "kriteria_led": "C2", "tabel_lkps": "2.D", "nama": "Rekognisi Lulusan",
        "deskripsi_singkat": "Sumber rekognisi (masyarakat, DUDI, prestasi mahasiswa), jenis pengakuan, per tahun.",
        "tipe": "tabel",
        "kolom_dibutuhkan": ["Sumber Rekognisi", "Jenis Pengakuan", "TS-2", "TS-1", "TS"],
        "sumber_data": "Rekap manual departemen",
        "status_ketersediaan": "perlu_input_manual", "mysql_table": None,
    },

    # ============== Kriteria C3 — Penelitian ==============
    "led_c3_penelitian": {
        "kriteria_led": "C3", "tabel_lkps": None, "nama": "C3 Penelitian",
        "deskripsi_singkat": "Sarpras, pembiayaan, roadmap penelitian, pengembangan DTPR, pelibatan mahasiswa, hibah, publikasi, HKI.",
        "tipe": "narasi", "kolom_dibutuhkan": list(_KOLOM_PPEPP),
        "sumber_data": "Kompilasi data Bagian 3 LKPS", "status_ketersediaan": "belum_tersedia", "mysql_table": None,
    },
    "lkps_3_a_1": {
        "kriteria_led": "C3", "tabel_lkps": "3.A.1", "nama": "Sarana Prasarana Penelitian",
        "deskripsi_singkat": "Nama lab/fasilitas, daya tampung, luas, kepemilikan, lisensi, daftar perangkat riset.",
        "tipe": "tabel",
        "kolom_dibutuhkan": ["Nama Lab/Fasilitas", "Daya Tampung", "Luas (m2)", "Status Kepemilikan",
                              "Status Lisensi", "Daftar Perangkat Riset", "Link Bukti"],
        "sumber_data": "SIMASET + pendataan mandiri departemen",
        "status_ketersediaan": "perlu_input_manual", "mysql_table": None,
    },
    "lkps_3_a_2": {
        "kriteria_led": "C3", "tabel_lkps": "3.A.2", "nama": "Penelitian DTPR, Hibah dan Pembiayaan",
        "deskripsi_singkat": "Nama DTPR, judul penelitian, mahasiswa terlibat, jenis hibah, peran, lingkup, durasi, nominal per tahun — per judul.",
        "tipe": "tabel",
        "kolom_dibutuhkan": ["Nama DTPR (Ketua)", "Judul Penelitian", "Jumlah Mahasiswa Terlibat", "Jenis Hibah",
                              "Peran (Ketua/Anggota)", "Lingkup (L/N/I)", "Durasi", "Nominal TS-2 (Rp juta)",
                              "Nominal TS-1 (Rp juta)", "Nominal TS (Rp juta)", "Link Bukti"],
        "sumber_data": "SIMASTER modul Penelitian",
        "status_ketersediaan": "perlu_input_manual", "mysql_table": None,
    },
    "lkps_3_a_3": {
        "kriteria_led": "C3", "tabel_lkps": "3.A.3", "nama": "Pengembangan DTPR Penelitian",
        "deskripsi_singkat": "Jenis pengembangan (pelatihan, sertifikasi profesi), nama DTPR penerima, jumlah dosen per tahun.",
        "tipe": "tabel",
        "kolom_dibutuhkan": ["Jenis Pengembangan", "Nama DTPR Penerima", "Jumlah Dosen TS-2", "Jumlah Dosen TS-1",
                              "Jumlah Dosen TS"],
        "sumber_data": "SIMBADA (simbada.dcseugm.id)",
        "status_ketersediaan": "perlu_input_manual", "mysql_table": None,
    },
    "lkps_3_a_4": {
        "kriteria_led": "C3", "tabel_lkps": "3.A.4", "nama": "Dukungan Institusi untuk DTPR",
        "deskripsi_singkat": "Jenis pembiayaan (keanggotaan organisasi profesi, dll.), nama DTPR, nominal dukungan per tahun.",
        "tipe": "tabel",
        "kolom_dibutuhkan": ["Jenis Pembiayaan", "Nama DTPR", "Nominal TS-2 (Rp juta)", "Nominal TS-1 (Rp juta)",
                              "Nominal TS (Rp juta)"],
        "sumber_data": "SIMBADA + rekap manual departemen",
        "status_ketersediaan": "perlu_input_manual", "mysql_table": None,
    },
    "lkps_3_c_1": {
        "kriteria_led": "C3", "tabel_lkps": "3.C.1", "nama": "Kerjasama Penelitian",
        "deskripsi_singkat": "Judul kerja sama, mitra, lingkup L/N/I, durasi, nominal per tahun, ciri khas PS — per kontrak.",
        "tipe": "tabel",
        "kolom_dibutuhkan": ["Judul Kerja Sama", "Mitra (Nama Institusi)", "Lingkup (L/N/I)", "Durasi (tahun)",
                              "Nominal per Tahun (Rp juta)", "Ciri Khas PS (Ya/Tidak)", "Link Bukti"],
        "sumber_data": "LENTERA SIMASTER (lentera.simaster.ugm.ac.id)",
        "status_ketersediaan": "perlu_input_manual", "mysql_table": None,
    },

    # ============== Kriteria C4 — Relevansi PkM ==============
    "led_c4_pkm": {
        "kriteria_led": "C4", "tabel_lkps": None, "nama": "C4 Relevansi PkM",
        "deskripsi_singkat": "Sarpras, DTPR, roadmap, hibah, kerja sama, diseminasi, HKI — struktur sama dengan C3 tapi untuk PkM.",
        "tipe": "narasi", "kolom_dibutuhkan": list(_KOLOM_PPEPP),
        "sumber_data": "Kompilasi data Bagian 4 LKPS", "status_ketersediaan": "belum_tersedia", "mysql_table": None,
    },
    "lkps_4_a_1": {
        "kriteria_led": "C4", "tabel_lkps": "4.A.1", "nama": "Sarana Prasarana PkM",
        "deskripsi_singkat": "Sama pola dengan 3.A.1 tapi untuk fasilitas PkM.",
        "tipe": "tabel",
        "kolom_dibutuhkan": ["Nama Lab/Fasilitas", "Daya Tampung", "Luas (m2)", "Status Kepemilikan",
                              "Status Lisensi", "Daftar Perangkat", "Link Bukti"],
        "sumber_data": "SIMASET + pendataan mandiri departemen",
        "status_ketersediaan": "perlu_input_manual", "mysql_table": None,
    },
    "lkps_4_c_1": {
        "kriteria_led": "C4", "tabel_lkps": "4.C.1", "nama": "Kerjasama PkM",
        "deskripsi_singkat": "Judul kerja sama, mitra, lingkup L/N/I, durasi, nominal per tahun, ciri khas PS — per kontrak.",
        "tipe": "tabel",
        "kolom_dibutuhkan": ["Judul Kerja Sama", "Mitra (Nama Institusi)", "Lingkup (L/N/I)", "Durasi (tahun)",
                              "Nominal per Tahun (Rp juta)", "Ciri Khas PS (Ya/Tidak)", "Link Bukti"],
        "sumber_data": "LENTERA SIMASTER (lentera.simaster.ugm.ac.id)",
        "status_ketersediaan": "perlu_input_manual", "mysql_table": None,
    },
    "lkps_4_c_2": {
        "kriteria_led": "C4", "tabel_lkps": "4.C.2", "nama": "Diseminasi Hasil PkM",
        "deskripsi_singkat": "Nama DTPR, judul kegiatan PkM, lingkup diseminasi L/N/I, tahun pelaksanaan, link bukti publikasi.",
        "tipe": "tabel",
        "kolom_dibutuhkan": ["Nama DTPR (Ketua)", "Judul Kegiatan PkM", "Lingkup Diseminasi (L/N/I)",
                              "TS-2", "TS-1", "TS", "Link Bukti Publikasi/Liputan"],
        "sumber_data": "simpan.ugm.ac.id / Google Drive + website departemen (dcse.fmipa.ugm.ac.id)",
        "status_ketersediaan": "perlu_input_manual", "mysql_table": None,
    },

    # ============== Kriteria C5 — Akuntabilitas ==============
    "led_c5_akuntabilitas": {
        "kriteria_led": "C5", "tabel_lkps": None, "nama": "C5 Akuntabilitas",
        "deskripsi_singkat": "Sistem tata kelola & tata pamong, standar mutu, efektivitas Audit Mutu Internal (AMI).",
        "tipe": "narasi", "kolom_dibutuhkan": list(_KOLOM_PPEPP),
        "sumber_data": "GJMA + SIMASTER EDPS", "status_ketersediaan": "belum_tersedia", "mysql_table": None,
    },

    # ============== Kriteria C6 — Diferensiasi Misi ==============
    "led_c6_diferensiasi_misi": {
        "kriteria_led": "C6", "tabel_lkps": None, "nama": "C6 Diferensiasi Misi",
        "deskripsi_singkat": "Kebijakan VMTS, rencana pengembangan strategis (ciri khas keilmuan PS), pengakuan dari masyarakat & DUDIKA.",
        "tipe": "narasi", "kolom_dibutuhkan": list(_KOLOM_PPEPP),
        "sumber_data": "Dokumen Renstra + testimoni DUDIKA", "status_ketersediaan": "belum_tersedia", "mysql_table": None,
    },
    "lkps_6": {
        "kriteria_led": "C6", "tabel_lkps": "6", "nama": "Kesesuaian Visi Misi",
        "deskripsi_singkat": "Teks visi & misi PT, UPPS, dan visi keilmuan PS — disandingkan untuk menunjukkan keselarasan.",
        "tipe": "tabel",
        "kolom_dibutuhkan": ["Level (PT/UPPS/PS)", "Teks Visi", "Teks Misi", "Catatan Keselarasan"],
        "sumber_data": "Dokumen Renstra PT/UPPS + SK Kurikulum PS",
        "status_ketersediaan": "perlu_input_manual", "mysql_table": None,
    },

    # ============== Kriteria D — Suplemen Program Studi ==============
    "lkps_d1": {
        "kriteria_led": "D", "tabel_lkps": "D1", "nama": "Mata Kuliah Inti Kekhasan",
        "deskripsi_singkat": "Daftar MK yang mencerminkan ciri khas keilmuan prodi (kode, nama, status wajib/pilihan, SKS, alasan).",
        "tipe": "tabel",
        "kolom_dibutuhkan": ["Kode MK", "Nama MK", "Status (Wajib/Pilihan)", "SKS", "Alasan Kekhasan"],
        "sumber_data": "Dokumen Kurikulum Prodi",
        "status_ketersediaan": "perlu_input_manual", "mysql_table": None,
    },
    "lkps_d2": {
        "kriteria_led": "D", "tabel_lkps": "D2", "nama": "Mata Kuliah Domain/Sektor Spesifik",
        "deskripsi_singkat": "MK yang menunjukkan penerapan pada sektor tertentu (mis. keamanan siber, transportasi).",
        "tipe": "tabel",
        "kolom_dibutuhkan": ["Kode MK", "Nama MK", "Sektor/Domain Penerapan", "SKS"],
        "sumber_data": "Dokumen Kurikulum Prodi",
        "status_ketersediaan": "perlu_input_manual", "mysql_table": None,
    },
    "lkps_d3": {
        "kriteria_led": "D", "tabel_lkps": "D3", "nama": "Mata Kuliah Metode Analisis",
        "deskripsi_singkat": "MK metodologi riset/analisis data pendukung kompetensi analitis lulusan.",
        "tipe": "tabel",
        "kolom_dibutuhkan": ["Kode MK", "Nama MK", "Metode Analisis yang Didukung", "SKS"],
        "sumber_data": "Dokumen Kurikulum Prodi",
        "status_ketersediaan": "perlu_input_manual", "mysql_table": None,
    },
}


def by_kriteria() -> dict[str, list[dict]]:
    """Item registry dikelompokkan per kriteria_led, urutan sesuai URUTAN_KRITERIA."""
    grouped: dict[str, list[dict]] = {k: [] for k in URUTAN_KRITERIA}
    for item_id, item in KEBUTUHAN_DATA.items():
        grouped.setdefault(item["kriteria_led"], []).append({**item, "id": item_id})
    return {k: grouped[k] for k in URUTAN_KRITERIA if k in grouped}


def _bagian_dari_tabel(tabel_lkps: str | None) -> str | None:
    """Token pertama sebelum '.' dari nomor tabel LKPS, kalau itu Bagian 1-6
    (mis. "2.B.4" -> "2", "6" -> "6"); None kalau tabel_lkps kosong atau bukan
    Bagian LKPS (mis. "D1"/"D2"/"D3", itu kekhasan LED, bukan LKPS)."""
    if not tabel_lkps:
        return None
    token = tabel_lkps.split(".")[0]
    return token if token in URUTAN_BAGIAN_LKPS else None


def dokumen_dari_item(item: dict) -> str:
    """"LKPS" kalau item itu tabel Bagian 1-6, selain itu "LED" (termasuk D1-D3)."""
    return "LKPS" if _bagian_dari_tabel(item["tabel_lkps"]) else "LED"


def led_items_by_kriteria() -> dict[str, list[dict]]:
    """Seperti by_kriteria(), difilter ke item dokumen LED saja (Umum/A/B/C1-C6/D)."""
    grouped = by_kriteria()
    return {
        k: [item for item in items if dokumen_dari_item(item) == "LED"]
        for k, items in grouped.items()
        if any(dokumen_dari_item(item) == "LED" for item in items)
    }


def lkps_items_by_bagian() -> dict[str, list[dict]]:
    """Item dokumen LKPS dikelompokkan per Bagian 1-6, urut nomor tabel_lkps."""
    grouped: dict[str, list[dict]] = {b: [] for b in URUTAN_BAGIAN_LKPS}
    for item_id, item in KEBUTUHAN_DATA.items():
        bagian = _bagian_dari_tabel(item["tabel_lkps"])
        if bagian:
            grouped[bagian].append({**item, "id": item_id})
    for bagian in grouped:
        grouped[bagian].sort(key=lambda item: item["tabel_lkps"])
    return {b: grouped[b] for b in URUTAN_BAGIAN_LKPS if grouped[b]}


def lkps_cuplikan_untuk_kriteria(kriteria_led: str) -> list[dict]:
    """Item dokumen LKPS ber-kriteria_led sama, urut nomor tabel -- dipakai
    subsection cuplikan read-only di tab LED (evidence PPEPP), lihat
    docstring modul poin 6."""
    items = [
        {**item, "id": item_id}
        for item_id, item in KEBUTUHAN_DATA.items()
        if item["kriteria_led"] == kriteria_led and dokumen_dari_item(item) == "LKPS"
    ]
    return sorted(items, key=lambda item: item["tabel_lkps"])


def ringkasan_status(item_ids: "set[str] | list[str] | None" = None, terisi_ids: set[str] | None = None) -> dict:
    """Hitung jumlah item per status_ketersediaan. `item_ids` membatasi item yang
    dihitung (default semua 49 -- dipakai untuk ringkasan per mode LED/LKPS).
    `terisi_ids` = set item_id yang sudah punya data di akreditasi_data_manual
    (dipakai bedakan 🟡 vs 🟠)."""
    terisi_ids = terisi_ids or set()
    subset = {k: v for k, v in KEBUTUHAN_DATA.items() if item_ids is None or k in item_ids}
    total = len(subset)
    tersedia_otomatis = sum(1 for v in subset.values() if v["status_ketersediaan"] == "tersedia_otomatis")
    perlu_manual = [k for k, v in subset.items() if v["status_ketersediaan"] == "perlu_input_manual"]
    perlu_manual_terisi = sum(1 for k in perlu_manual if k in terisi_ids)
    belum_tersedia = sum(1 for v in subset.values() if v["status_ketersediaan"] == "belum_tersedia")
    return {
        "total": total,
        "tersedia_otomatis": tersedia_otomatis,
        "perlu_manual_total": len(perlu_manual),
        "perlu_manual_terisi": perlu_manual_terisi,
        "belum_tersedia": belum_tersedia,
        "lengkap": tersedia_otomatis + perlu_manual_terisi,
    }


def badge_status(item_id: str, ada_data: bool) -> str:
    """Badge status satu item untuk ditampilkan di dashboard."""
    status = KEBUTUHAN_DATA[item_id]["status_ketersediaan"]
    if status == "tersedia_otomatis":
        return "🟢"
    if status == "perlu_input_manual":
        return "🟡" if ada_data else "🟠"
    return "🔴"
