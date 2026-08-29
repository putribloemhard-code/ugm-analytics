# Listing Ide: Analisis Dampak UGM (Kepmen 361/M/KEP/2025 & SDGs)

Sumber indikator: Keputusan Menteri Pendidikan Tinggi, Sains, dan Teknologi Nomor 361/M/KEP/2025 tentang Indikator Dampak Sosial, Ekonomi, dan Lingkungan Perguruan Tinggi.
Sumber SDG: 17 Tujuan Pembangunan Berkelanjutan (SDGs) versi PBB — dipakai versi internasional umum, bukan pemetaan resmi UGM (perlu dicek ke BTD apakah ada versi resmi UGM sendiri).

---

## 1. Mata Kuliah → Integrasi Kurikulum Sustainability

**Kategori & Indikator Resmi**
- Dampak: **Lingkungan**, Tema 5 (Pendidikan dan Penelitian)
- Indikator: Jumlah mata kuliah/modul terkait *sustainability* dan biodiversitas
- Formula: Jumlah mata kuliah/modul terkait ÷ periode berjalan (satuan: mata kuliah/modul)

**Data yang dibutuhkan**
- Nama mata kuliah, deskripsi/silabus singkat, fakultas/prodi pengampu
- (Opsional) jumlah SKS, status wajib/pilihan

**Sumber data**
- Halaman kurikulum tiap prodi di website fakultas (publik, tapi formatnya beda-beda tiap fakultas)
- Alternatif lebih efisien: minta akses data terpusat dari SIMASTER (kalau BTD bisa fasilitasi)

**Cara processing**
1. Scrape/kumpulkan deskripsi tiap mata kuliah
2. Keyword matching ke daftar topik resmi Kepmen: pembangunan berkelanjutan, perubahan iklim, energi terbarukan, pengelolaan limbah, ekonomi sirkular, konservasi lingkungan, keanekaragaman hayati, rehabilitasi/restorasi lingkungan, pengelolaan SDA
3. Tandai mata kuliah yang match sebagai "terkait sustainability", hitung per prodi/fakultas

**Output**
- Bar chart: jumlah mata kuliah terkait sustainability per fakultas
- Tabel drill-down: daftar mata kuliah yang masuk kategori ini per prodi
- Tren dari waktu ke waktu (kalau data multi-tahun tersedia)

**SDG Relevan — pemetaan per topik (bukan cuma 1 SDG umum)**

Kepmen 361/M/KEP/2025 mencantumkan 9 topik resmi untuk indikator ini (Kriteria indikator no. 5, Tema Pendidikan dan Penelitian — cek dokumen PDF halaman ke-32, sub-poin a-j). Tiap topik dipetain ke SDG spesifik (internasional, karena Kepmen sendiri tidak mencantumkan nomor SDG):

| Topik Resmi Kepmen | SDG | Nama SDG |
|---|---|---|
| Perubahan iklim | 13 | Penanganan Perubahan Iklim |
| Energi terbarukan | 7 | Energi Bersih dan Terjangkau |
| Pengelolaan limbah | 12 | Konsumsi dan Produksi Bertanggung Jawab |
| Ekonomi sirkular | 12 | Konsumsi dan Produksi Bertanggung Jawab |
| Konservasi lingkungan | 15 | Ekosistem Daratan |
| Keanekaragaman hayati | 15 | Ekosistem Daratan (atau 14 kalau spesifik laut) |
| Rehabilitasi dan restorasi lingkungan | 15 | Ekosistem Daratan |
| Pengelolaan sumber daya alam | 6 / 2 / 15 | Air Bersih (6), Tanpa Kelaparan (2 — kalau soal pangan/pertanian), atau Ekosistem Daratan (15), tergantung SDA yang dibahas |
| Pembangunan berkelanjutan (umum) | — | Istilah payung, tidak dipetakan ke 1 SDG spesifik — lihat konten lain di deskripsi mata kuliah untuk menentukan SDG-nya |

**Catatan penting**:
- 1 mata kuliah bisa dapat lebih dari 1 SDG sekaligus (contoh: mata kuliah "Pengelolaan Limbah B3 dan Dampaknya terhadap Ekosistem Perairan" → SDG 12 dan SDG 14 sekaligus)
- Topik "pembangunan berkelanjutan" dan "pengelolaan sumber daya alam" sengaja tidak dipetakan ke satu SDG tunggal karena cakupannya luas — perlu keyword tambahan yang lebih spesifik dari isi deskripsi mata kuliah itu sendiri

**Kamus keyword per SDG** (dipakai untuk keyword matching otomatis):
```python
MATKUL_SDG_KEYWORD = {
    13: {'nama': 'Penanganan Perubahan Iklim',
         'keywords': ['perubahan iklim', 'climate change', 'pemanasan global',
                      'global warming', 'mitigasi iklim', 'adaptasi iklim']},
    7:  {'nama': 'Energi Bersih dan Terjangkau',
         'keywords': ['energi terbarukan', 'renewable energy', 'energi bersih',
                      'energi surya', 'energi angin', 'biomassa energi']},
    12: {'nama': 'Konsumsi dan Produksi Bertanggung Jawab',
         'keywords': ['pengelolaan limbah', 'waste management', 'ekonomi sirkular',
                      'circular economy', 'daur ulang', 'recycling',
                      'konsumsi berkelanjutan', 'produksi bersih']},
    15: {'nama': 'Ekosistem Daratan',
         'keywords': ['keanekaragaman hayati', 'biodiversitas', 'biodiversity',
                      'konservasi lingkungan', 'konservasi hutan', 'restorasi lahan',
                      'rehabilitasi lahan', 'ekosistem darat', 'flora fauna']},
    14: {'nama': 'Ekosistem Lautan',
         'keywords': ['ekosistem laut', 'konservasi laut', 'restorasi mangrove',
                      'pesisir', 'kelautan', 'marine ecosystem', 'terumbu karang']},
    6:  {'nama': 'Air Bersih dan Sanitasi',
         'keywords': ['pengelolaan air', 'water management', 'sanitasi',
                      'kualitas air', 'daur ulang air']},
    2:  {'nama': 'Tanpa Kelaparan',
         'keywords': ['ketahanan pangan', 'food security', 'pertanian berkelanjutan',
                      'sustainable agriculture']},
}

def map_matkul_ke_sdg(deskripsi_matkul):
    """Cek deskripsi mata kuliah, kembalikan daftar SDG yang match (bisa lebih dari 1)."""
    teks = deskripsi_matkul.lower()
    hasil = []
    for sdg_num, info in MATKUL_SDG_KEYWORD.items():
        if any(kw in teks for kw in info['keywords']):
            hasil.append({'sdg': sdg_num, 'nama': info['nama']})
    return hasil
```

---

## 2. Sebaran KKN → Desa Binaan

**Kategori & Indikator Resmi**
- Dampak: **Sosial**, Tema 3 (Pengabdian dan Pengembangan Masyarakat)
- Indikator: Jumlah desa binaan aktif pada program pengabdian dan pengembangan masyarakat
- Formula: Jumlah desa binaan yang memenuhi kriteria "aktif" (satuan: desa)
- Kriteria aktif: ada MoU/MoA/PKS berlaku, ≥1 program di tahun pelaporan, ada bukti pendampingan, program ≥6 bulan/berkelanjutan

**Data yang dibutuhkan**
- Nama desa/lokasi KKN, periode pelaksanaan, deskripsi program kerja, fakultas/kelompok yang terlibat
- Status kerja sama (MoU/tidak) — penting buat bedakan "desa binaan" vs "desa dikunjungi sekali"

**Sumber data**
- `kkn.ugm.ac.id`, `pengabdian.ugm.ac.id/wilayah-binaan/` — perlu dicek langsung ketersediaan datanya
- Kalau nggak terstruktur publik, mungkin perlu laporan KKN per periode dari LPPM/unit KKN

**Cara processing**
1. Kumpulkan daftar desa + deskripsi program per periode KKN
2. Geocoding nama desa/kabupaten → koordinat (pakai API gratis, misal Nominatim/OpenStreetMap)
3. Cek desa mana yang muncul berulang lintas periode (indikasi "binaan" vs "sekali kunjung")
4. Keyword matching deskripsi program → kategori dampak (pendidikan, kesehatan, ekonomi, lingkungan, dst)

**Output**
- Peta interaktif sebaran lokasi KKN (Plotly/Folium)
- Highlight visual desa binaan aktif (berulang) vs desa yang cuma sekali dikunjungi
- Breakdown jenis program per desa/wilayah

**SDG Relevan**
- **SDG 1** — Tanpa Kemiskinan (program pemberdayaan ekonomi desa)
- **SDG 11** — Kota dan Permukiman yang Berkelanjutan (pembangunan desa binaan)
- **SDG 17** — Kemitraan untuk Mencapai Tujuan (kerja sama PT-desa lewat MoU)

---

## 3. Berita UGM → Program Rehabilitasi Lingkungan (dan dampak lain)

**Kategori & Indikator Resmi (contoh utama: "menanam pohon")**
- Dampak: **Lingkungan**, Tema 4 (Keanekaragaman Hayati)
- Indikator: Jumlah program rehabilitasi dan restorasi lingkungan
- Formula: Jumlah program rehabilitasi & restorasi lingkungan PT pada periode berjalan (satuan: program)
- Cakupan: penanaman pohon/reboisasi, rehabilitasi lahan kritis, restorasi hutan/mangrove/sungai, pemulihan kualitas tanah/air/udara, pengendalian erosi/banjir, ruang terbuka hijau

**Data yang dibutuhkan**
- Judul berita, isi/ringkasan berita, tanggal publikasi, link sumber
- Entitas hasil NER: aktor (ORG/PER), aksi (kata kerja: menanam/merestorasi/membangun), lokasi (GPE/LOC), jumlah/skala (QTY/CRD — misal "1000 pohon")

**Sumber data**
- **RSS resmi UGM** (`ugm.ac.id/en/feed/` atau `/id/feed/`) — untuk berita terbaru, di-polling berkala lewat `scripts/ingest.py`
- **Sitemap UGM** (`ugm.ac.id/sitemap.xml` → `post-sitemap2.xml` s/d `post-sitemap33.xml`) — untuk backfill data historis 2007-sekarang, diambil lewat `scripts/backfill_sitemap.py` (ekstrak meta tag `og:title`/`og:description`/`article:published_time` dari tiap halaman artikel)
- Kedua sumber disimpan ke tabel `berita` yang sama di `ugm_news.duckdb`, diproses lewat `scripts/process_nlp.py` (NER + klasifikasi topik)

**Cara processing**
1. NER (sudah ada) — ekstrak entitas ORG/LOC/QTY dari berita
2. **Tambahan baru**: ekstraksi aksi/predikat — keyword matching kata kerja ("menanam", "merestorasi", "membangun", dst) ke kategori program sesuai daftar Kepmen di atas
3. Deduplikasi — 1 program yang diberitakan berkali-kali dihitung 1 kali (bukan per artikel)
4. Klasifikasi tambahan untuk berita non-lingkungan ke indikator lain (prestasi mahasiswa, kebijakan publik, kolaborasi riset — lihat Kepmen Tema 1 & 4 Dampak Sosial)

**Output**
- Dashboard tren "program berdampak" dari waktu ke waktu
- Breakdown per kategori indikator (rehabilitasi lingkungan, prestasi mahasiswa, kebijakan publik, dst)
- Peta lokasi kegiatan (kalau lokasi disebut di berita)

**SDG Relevan**
- **SDG 13** — Penanganan Perubahan Iklim
- **SDG 15** — Ekosistem Daratan (untuk penanaman pohon/reboisasi/konservasi darat)
- **SDG 14** — Ekosistem Lautan (kalau kegiatan terkait mangrove/pesisir/laut)

---

## 4. Asal Mahasiswa → Keterserapan Kelompok Afirmasi

**Kategori & Indikator Resmi**
- Dampak: **Sosial**, Tema 1 (Pendidikan Inklusif)
- Indikator: Persentase lulusan kelompok afirmasi (ekonomi tidak mampu, disabilitas, daerah 3T) mendapat pekerjaan/wirausaha/lanjut studi dalam 1 tahun
- Formula: Total lulusan kelompok afirmasi ÷ Total lulusan yang langsung bekerja × 100%
- **Catatan penting**: indikator resminya BUKAN soal asal daerah mahasiswa secara umum, tapi spesifik kelompok afirmasi (3T/ekonomi tidak mampu/disabilitas)

**Data yang dibutuhkan**
- Status kelompok afirmasi tiap mahasiswa (penerima KIP-K/Bidikmisi/SKTM, disabilitas, asal daerah 3T resmi Kemendesa PDTT)
- Status kelulusan + hasil tracer study (bekerja/wirausaha/lanjut studi dalam 1 tahun)

**Sumber data**
- 🔴 **Sensitif** — kemungkinan besar tidak ada versi publik. Butuh akses resmi ke tracer study & SIMASTER, kemungkinan cuma bisa dalam bentuk agregat karena alasan privasi

**Cara processing**
- Agregasi persentase per kategori afirmasi, per fakultas/prodi
- (Kalau data tersedia dalam bentuk agregat resmi) hitung langsung sesuai formula Kepmen

**Output**
- Bar chart persentase keterserapan lulusan per kategori afirmasi
- Perbandingan antar fakultas/prodi (dalam bentuk agregat, bukan data individu)

**SDG Relevan**
- **SDG 4** — Pendidikan Berkualitas (akses pendidikan setara)
- **SDG 10** — Berkurangnya Kesenjangan (kelompok afirmasi/rentan)
- **SDG 1** — Tanpa Kemiskinan (mahasiswa ekonomi tidak mampu)

**Rekomendasi**: ide ini realistisnya dikerjakan **paling akhir**, tunggu kejelasan izin akses resmi.

---

---

## 5. Berita → Ekosistem Kewirausahaan (Startup/Spin-off UGM)

**Kategori & Indikator Resmi**
- Dampak: **Ekonomi**, Tema 3 (Ekosistem Kewirausahaan)
- Indikator: Jumlah spin-off/start-up yang lahir dari perguruan tinggi
- Formula: Jumlah perusahaan yang lahir dari PT (satuan: entitas)

**Data yang dibutuhkan**
- Judul + isi berita yang menyebut peluncuran startup/spin-off/unit usaha baru
- Entitas: nama startup, aktor pendiri (dosen/mahasiswa/unit), tanggal peluncuran

**Sumber data**
- Sama seperti idea 3 — RSS resmi UGM (`ugm.ac.id/en/feed/` atau `/id/feed/`) untuk berita terbaru + Sitemap UGM (`ugm.ac.id/sitemap.xml`, file `post-sitemap2.xml` s/d `post-sitemap33.xml`) untuk data historis, keduanya masuk tabel `berita` di `ugm_news.duckdb`

**Cara processing**
1. Extend `KATEGORI_KEYWORD` (di `scripts/keywords.py`) — tambah kategori baru `'kewirausahaan'` dengan kata kunci: "startup", "spin-off", "diluncurkan", "inkubasi bisnis", "unit usaha"
2. Filter berita yang topiknya match kategori ini
3. Ekstrak nama startup dari entitas ORG hasil NER

**Output**
- Counter jumlah startup/spin-off terdeteksi per tahun
- Tabel nama startup + deskripsi singkat + tanggal peluncuran

**SDG Relevan**
- SDG 8 — Pekerjaan Layak dan Pertumbuhan Ekonomi
- SDG 9 — Industri, Inovasi, dan Infrastruktur

---

## 6. Berita (Entitas EVT) → Kunjungan Akademik

**Kategori & Indikator Resmi**
- Dampak: **Ekonomi**, Tema 4 (Kunjungan Akademik dan Pengeluaran Pengunjung)
- Indikator: Jumlah kunjungan terkait universitas (wisata akademik, konferensi, gathering alumni)
- Formula: Jumlah kunjungan/event per tahun

**Data yang dibutuhkan**
- Entitas berlabel `EVT` (event) hasil NER — nama event, tanggal, deskripsi singkat dari berita

**Sumber data**
- Sama seperti idea 3 — RSS + Sitemap UGM, sudah masuk tabel `berita` di `ugm_news.duckdb`
- Field yang dipakai spesifik: kolom `entitas` yang berisi hasil NER berlabel `(EVT)`, sudah diproses `scripts/process_nlp.py`

**Cara processing**
1. Query kolom `entitas` di tabel `berita`, filter yang mengandung label `(EVT)`
2. Kategorikan mana yang "event akademik publik" (seminar, konferensi, wisuda, gathering alumni) vs event internal biasa — pakai keyword tambahan
3. Agregasi jumlah per tahun

**Output**
- Tren jumlah event akademik UGM per tahun (extend dari chart "Event/Kegiatan Paling Sering Disebut" yang sudah ada di dashboard News Intelligence)

**SDG Relevan**
- SDG 8 — Pekerjaan Layak dan Pertumbuhan Ekonomi
- SDG 11 — Kota dan Permukiman yang Berkelanjutan

---

## 7. Berita (Topik "Kerjasama") → Kolaborasi Riset-Industri

**Kategori & Indikator Resmi**
- Dampak: **Ekonomi**, Tema 2 (Penelitian dan Pertukaran Pengetahuan)
- Indikator: Kolaborasi riset dengan industri/pemerintah — jumlah kontrak kerja sama riset
- Formula: Jumlah kontrak kerjasama riset per tahun

**Data yang dibutuhkan**
- Berita berlabel topik `kerjasama` (dari kolom `topik` di tabel `berita`) yang juga menyebut kata "riset"/"penelitian"/"R&D"
- Entitas mitra (ORG) — nama perusahaan/instansi pemerintah yang terlibat

**Sumber data**
- Sama seperti idea 3 — RSS + Sitemap UGM, tabel `berita` di `ugm_news.duckdb`
- Field yang dipakai spesifik: kolom `topik` (hasil `classify_topic()` di `scripts/keywords.py`, sudah ada kategori `'kerjasama'`)

**Cara processing**
1. Query tabel `berita` WHERE `topik = 'kerjasama'`
2. Filter lagi yang teksnya juga mengandung kata "riset"/"penelitian"/"R&D" (bedakan dari kerjasama non-riset, misal kerjasama pendidikan/pertukaran pelajar)
3. Ekstrak entitas ORG sebagai nama mitra

**Output**
- Jumlah kolaborasi riset-industri per tahun
- Breakdown mitra (perusahaan vs instansi pemerintah vs universitas asing)

**SDG Relevan**
- SDG 9 — Industri, Inovasi, dan Infrastruktur
- SDG 17 — Kemitraan untuk Mencapai Tujuan

---

## Ringkasan Prioritas Realistis

| Prioritas | Ide | Kategori Dampak | Sumber Data | Alasan |
|---|---|---|---|---|
| 1 | Berita — Rehabilitasi Lingkungan | Lingkungan | RSS + Sitemap (sudah ada) | Pipeline sudah jalan, tinggal extend keyword |
| 1 | Berita — Kunjungan Akademik (EVT) | Ekonomi | RSS + Sitemap (sudah ada) | Reuse entitas EVT yang sudah ter-extract |
| 1 | Berita — Kolaborasi Riset (kerjasama) | Ekonomi | RSS + Sitemap (sudah ada) | Reuse topik kerjasama yang sudah ter-extract |
| 2 | Berita — Ekosistem Kewirausahaan | Ekonomi | RSS + Sitemap (sudah ada) | Perlu tambah 1 kategori keyword baru |
| 2 | Mata Kuliah | Lingkungan | Scrape kurikulum fakultas | Data kemungkinan bisa dikumpulin publik |
| 3 | Sebaran KKN | Sosial | kkn.ugm.ac.id / pengabdian.ugm.ac.id | Perlu riset ketersediaan data dulu |
| 4 | Asal Mahasiswa (afirmasi) | Sosial | Tracer study / SIMASTER | Data sensitif, butuh akses resmi |