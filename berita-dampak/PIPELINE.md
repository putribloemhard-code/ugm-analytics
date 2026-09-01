# PIPELINE — Analisis Dampak Berita UGM (berita-dampak)

## Tujuan

Mengidentifikasi dan memetakan berita dampak UGM pada 4 tema:
rehabilitasi lingkungan, kewirausahaan, kunjungan akademik, kolaborasi riset.
Sumber data: situs publik ugm.ac.id (RSS + sitemap). Bukan eLOK.

## Penyimpanan data

**MySQL** (database `ugm_analytics`, semua tabel berprefix `berita_`) —
migrasi penuh dari DuckDB selesai (2026-08-29); tidak ada lagi file
`.duckdb` di pipeline ini. Koneksi lewat `scripts/db.py` (`get_engine()`,
`pool_pre_ping=True`, `pool_recycle=3600`). Penulisan baris-per-item (sitemap,
berita) pakai `upsert()` — INSERT ... ON DUPLICATE KEY UPDATE per batch
~100 baris, dibungkus retry 3× — supaya proses panjang (`fetch_detail.py`
bisa jalan berjam-jam untuk ribuan URL) tidak kehilangan data kalau berhenti
di tengah jalan, dan running ulang tidak menghasilkan duplikat. Tabel
ringkasan/agregat tetap full-replace (`to_sql(if_exists="replace")`) tiap run.

## Alur processing

1. **Backfill sitemap** — `scripts/backfill_sitemap.py`
   Ambil seluruh `post-sitemapN.xml` dari `https://ugm.ac.id/wp-sitemap.xml`.
   Upsert (url, lastmod) ke tabel `berita_sitemap` di MySQL.
   Idempoten (ON DUPLICATE KEY UPDATE lastmod), ada retry otomatis per sitemap.
   Hasil: ~32.000 URL berita (2007–2026).

2. **Ingest RSS** — `scripts/ingest.py`
   Ambil feed `https://ugm.ac.id/id/feed/` dan `/en/feed/` (10 item masing-masing)
   dengan judul, tanggal, kategori, deskripsi. Upsert ke tabel `berita_berita` (sumber='rss').

3. **Fetch detail** — `scripts/fetch_detail.py`
   Filter URL sitemap yang slug-nya cocok kata kunci tema (ID+EN) lewat
   `REGEXP` (MySQL), lalu fetch halaman untuk mengambil judul (h1), deskripsi
   (meta description), tanggal (datePublished), DAN isi lengkap artikel +
   kredit redaksional lewat `fetch_full()` yang di-IMPORT dari
   `scripts/fetch_backlog.py` (sumber tunggal logika ekstraksi isi/kredit --
   JANGAN duplikat). Upsert ke tabel `berita_berita` (sumber='sitemap') per
   batch 100 baris; throttle ringan + retry jaringan (request) + retry MySQL
   (batch upsert). Kandidat = slug cocok kata kunci tema DAN `isi` masih
   kosong (bukan sekadar "baris belum ada") -- supaya artikel yang baru
   masuk lewat ingest.py (RSS, cuma judul+deskripsi pendek) ikut ke-refetch
   dan otomatis dapat isi/kredit juga, tanpa backfill manual (bug diperbaiki
   2026-09-01 -- sebelumnya fetch_detail.py TIDAK mengisi isi/kredit sama
   sekali, cuma judul+deskripsi, sampai backlog 32.130 URL penuh dijalankan
   manual lewat `fetch_backlog.py`; lihat bagian "Isi lengkap artikel" di
   bawah).

4. **Normalisasi** — `scripts/normalisasi.py`
   Bersihkan teks, konversi tanggal (RFC 822 / ISO 8601 → YYYY-MM-DD),
   buang duplikat URL dan baris tanpa judul. DELETE + INSERT ulang dalam
   SATU transaksi MySQL (bukan dua langkah terpisah) — kalau gagal di
   tengah, rollback otomatis mengembalikan tabel ke kondisi sebelumnya,
   bukan tabel kosong.

5. **Tagging tema** — `scripts/process_nlp.py`
   Substring match (case-insensitive) kamus `scripts/keywords.py`
   terhadap judul + deskripsi. Satu berita bisa multi-tema.
   Output: tabel `berita_topik` (url, topik) dan `ringkasan_topik_tahun`.

6. **Tagging Kepmen & SDG — SEMUA tema (14 tema)** — `scripts/tag_kepmen_all.py`
   Map tiap berita ke 14 tema resmi Kepmen 361/M/KEP/2025: 4 tema inti
   (rehabilitasi_lingkungan, kewirausahaan, kunjungan_akademik, kolaborasi_riset
   — keyword dari `scripts/keywords.py`) + 10 tema lain (pendidikan inklusif,
   penelitian & inovasi, pengabdian masyarakat, instansi publik, pengajaran &
   pembelajaran, pengeluaran institusi, energi, limbah, transportasi — keyword dari
   `TEMA_KEPMEN_LENGKAP` di `scripts/kepmen_sdg.py`). Tiap tema membawa pilar
   (Lingkungan/Ekonomi/Sosial) + klaster SDGs resmi dari `UGM Analytics.xlsx`
   (sheet "Konten UGM Berdampak" & "#Ref").
   Output tabel baru (menggantikan berita_kepmen/berita_sdg sebagai sumber
   dashboard):
   - `berita_kepmen_all` (url, topik, dampak, topik_kepmen, sdg '13|14|15')
   - `berita_sdg_all` (url, sdg — dedup per url)
   - `ringkasan_topik_all` (topik, dampak, topik_kepmen, sdg, jumlah_berita)
   - `ringkasan_pilar` (dampak, jumlah_berita)
   - `ringkasan_pilar_tahun` (dampak, tahun, jumlah_berita)
   - `ringkasan_sdg_all` (sdg, nama_sdg, jumlah_berita)
   Tabel lama (berita_kepmen, berita_sdg, berita_kepmen_lengkap,
   ringkasan_kepmen_lengkap) tetap ada di MySQL (sisa sinkronisasi lama)
   tapi sudah tidak ditulis ulang oleh script apa pun sejak tag_kepmen_berita.py
   dan tag_kepmen_lengkap.py dihapus (2026-08-29, lihat migrasi MySQL di bawah)
   -- aman diabaikan atau di-drop manual, dashboard tidak pernah membacanya.

6b. **Tagging SDG LANGSUNG seluruh sitemap** — `scripts/tag_sdg_langsung.py`
   (mode dashboard "SDGs saja"). SEMUA 32.130 URL sitemap dipetakan ke 17 SDG
   TANPA tema dampak: kata-kata slug URL (27.343 yang belum di-fetch) +
   judul & deskripsi (4.787 yang sudah). Kamus: `scripts/sdg_keywords.py`
   (17 SDG, ID+EN, sumber nama resmi & target SDG; keyword ≤5 huruf pakai
   word-boundary). Output: `sitemap_sdg` (url, sdg), `ringkasan_sdg_sitemap`,
   `ringkasan_sdg_sitemap_tahun`. Hasil (2026-08-21): 22.499 pasangan,
   15.688 / 32.130 URL (48,8%) bertanda >=1 SDG.

6c. **Narasi LLM** — `scripts/generate_narasi_llm.py` (opsional, setelah
   tagging selesai). Merangkai angka yang sudah dihitung pandas jadi narasi
   Bahasa Indonesia via Gemini API, cache ke `berita_narasi_cache`. Skip
   aman (exit 0) kalau `GEMINI_API_KEY` belum diisi atau API gagal --
   dashboard fallback ke narasi template.

6d. **Tagging Fakultas/Unit Kerja** — `scripts/tag_unit_kerja.py` (independen
   dari tagging Kepmen/SDG di atas -- lapisan terpisah, tidak mengubah tabel
   manapun yang sudah ada). Substring match nama resmi 44 fakultas/sekolah/
   unit kerja UGM (`scripts/unit_kerja.py`) terhadap judul + deskripsi;
   sengaja TIDAK memakai singkatan (FEB/FT/FH/dst), cuma nama resmi penuh --
   lihat catatan false-positive-prone di docstring script. Guard leakage
   lintas-universitas: occurrence yang langsung diikuti "Universitas <nama
   lain>" (bukan Gadjah Mada) di-skip, mis. "Fakultas Pertanian Universitas
   Negeri Gorontalo" TIDAK dihitung sebagai Fakultas Pertanian UGM (lihat
   `_match_valid()`). Output: `berita_unit_kerja` (url, unit_kerja,
   kategori). Hasil backfill (2026-09-01, setelah guard leakage): 785
   pasangan url-unit; 748 / 4.806 berita (15,6%) match >=1 unit (sebelum
   guard: 789 pasangan, 751 berita).

6e. **Isi lengkap artikel** — `scripts/fetch_backlog.py` (backfill besar,
   dijalankan manual/background, BUKAN bagian STEPS update_mingguan.py --
   fetch_detail.py di atas yang menjaga cakupan tetap penuh utk artikel baru
   tiap minggu). Ekstraksi 2 tingkat dari `div.inner-content` (tervalidasi
   manual 17 sampel lintas 2008-2026, kedua pola URL id/berita + en/news):
   (1) `<p>`/`<li>` -- mayoritas artikel; (2) fallback child `<div>` polos
   langsung kalau tidak ada `<p>` sama sekali -- template lama (~2010-2016an)
   yang taruh tiap paragraf di `<div>` tanpa `<p>` (ditemukan 2026-09-01,
   sempat bikin 265/274 baris isi-nya kosong padahal kontennya ADA, bukan
   soal jaringan). Baris kredit trailing ("Penulis:"/"Reportase:"/"Author:"/
   "Editor:"/"Post-editor:"/"Foto:"/dst.) dipisah ke kolom `kredit` (nullable;
   default aman: kalau pola tidak jelas, semua tetap masuk `isi`). `kredit`
   SENGAJA TIDAK ikut di keyword matching (tag_kepmen_all.py/tag_sdg_langsung.py/
   tag_unit_kerja.py/process_nlp.py, lewat `db.column_exists()` fallback aman
   kalau kolom belum ada) -- byline redaksional bisa salah men-tag unit yang
   cuma menerbitkan, bukan yang dibahas.

   Retry cap: kolom `fetch_gagal_count` (INT, default 0) naik tiap kali isi
   masih kosong sesudah fetch (request gagal ATAU halaman genuinely tanpa
   konten yang bisa diekstrak, mis. artikel yang paragrafnya di `<h3>` --
   kasus langka, 1 dari 274); begitu >=3x, URL itu berhenti otomatis
   dicoba lagi tiap minggu (lihat `MAX_GAGAL`/`bump_fail_counts()` di
   fetch_backlog.py). Baris yang belum pernah ada sama sekali TIDAK kena
   counter -- artikel benar-benar baru yang gagal di percobaan pertama
   tetap dicoba lagi minggu depan.

   Hasil backfill (2026-09-01): 32.160 URL awal -> 31.900 isi terisi (369
   kosong: 265 karena template `<div>` di atas + 8 timeout + sisanya
   perbedaan hitung race sitemap yang terus bertambah). Setelah fallback
   `<div>` + backfill_sitemap.py susulan (menangkap sitemap terbaru):
   32.192 baris, **32.190 isi terisi (99,99%)**, cuma 2 baris tersisa
   (masing-masing baru gagal 1x, belum kena cap).

   `normalisasi.py` digeneralisasi (2026-09-01): DELETE+INSERT ulangnya
   sekarang otomatis passthrough SEMUA kolom di luar 6 kolom inti
   (url/judul/tanggal/deskripsi/kategori/sumber) apa adanya -- bukan
   hardcode daftar isi/kredit lagi. Ini investasi ke depan: kolom baru
   apapun yang ditambah script lain nanti otomatis aman dari DELETE+INSERT
   ini, tidak perlu tambal manual lagi (sudah 2x jadi bug nyata: isi/kredit,
   lalu fetch_gagal_count).

7. **Output**
   - `dashboard_berita_dampak.py` — Streamlit interaktif dengan filter global
     (tahun, tema, sumber). Bagian: ringkasan, distribusi per tema,
     peta Tema Resmi Kepmen & klaster SDGs (bar + heatmap tema×SDG),
     heatmap tema×tahun, tren tahunan, tren bulanan (musiman),
     cakupan vs total berita UGM (baseline sitemap), breakdown keyword match,
     multi-tema, word frequency per tema, daftar berita (dengan kolom
     Tema Kepmen & SDG), cek manual.
   - `scripts/laporan_static.py` → `laporan_berita_dampak.html`
     (plotly write_html, JS inline — render tanpa internet)

## Run commands (dari folder berita-dampak)

```bash
../venv/Scripts/python.exe scripts/backfill_sitemap.py
../venv/Scripts/python.exe scripts/ingest.py
../venv/Scripts/python.exe scripts/fetch_detail.py   # lama: ~4.700 halaman
../venv/Scripts/python.exe scripts/normalisasi.py
../venv/Scripts/python.exe scripts/process_nlp.py
../venv/Scripts/python.exe scripts/tag_kepmen_all.py   # 14 tema + SDG (utama)
../venv/Scripts/python.exe scripts/tag_unit_kerja.py    # 44 fakultas/sekolah/unit kerja
../venv/Scripts/python.exe scripts/tag_sdg_langsung.py  # mode "SDGs saja"
../venv/Scripts/python.exe scripts/generate_narasi_llm.py  # opsional, butuh GEMINI_API_KEY
../venv/Scripts/python.exe scripts/laporan_static.py
streamlit run dashboard_berita_dampak.py
```

Atau jalankan semuanya sekaligus (urutan sudah benar, dengan lock file):
`../venv/Scripts/python.exe scripts/update_mingguan.py`

## Hasil (terakhir dijalankan: 2026-08-20)

- sitemap: 32.130 URL berita (2005–2026)
- berita di tabel: 4.787 (20 dari RSS, sisanya fetch detail sitemap)
- tagging 14 tema Kepmen (tag_kepmen_all.py):
  - 2.481 baris url–tema; 1.969 berita unik match ≥1 tema (41% dari 4.787)
  - per pilar: Lingkungan 1.094, Sosial 631, Ekonomi 577
  - per tema: rehabilitasi lingkungan 653, limbah 379, kewirausahaan 374,
    pengabdian masyarakat 374, penelitian & inovasi 179, kolaborasi riset 138,
    instansi publik 124, energi 109, kunjungan akademik 70, belanja UMKM 31,
    pendidikan inklusif 20, transportasi 15
  - SDG terbanyak: SDG 13 (755), SDG 8 (703), SDG 9 (659), SDG 14 (651),
    SDG 15 (651), SDG 17 (608), SDG 1 (538), SDG 11 (457), SDG 12 (408)
- 2026-08-20 (perluasan keyword): keywords.py + TEMA_KEPMEN_LENGKAP diperluas
  (hutan/forest/kehutanan/mangrove → rehabilitasi; entrepreneur/research
  collaboration/joint research → ekonomi; community service/kementerian/solar/
  plastic/plastik → tema terkait). Hasil: 1.181 → 1.969 berita unik.
  Kandidat yang DITOLAK karena false positive: delegation (prestasi lomba),
  desa/village (generik), kebijakan/policy (generik), nuclear.
- 2026-08-20 (update otomatis): `scripts/update_mingguan.py` menjalankan
  pipeline lengkap (lock file data/.update_lock mencegah tumpang tindih);
  dashboard punya tombol "🔄 Update Berita Terbaru" (sidebar, jalankan
  background); cron Hermes Sabtu 06:00 (update_berita_dampak.sh).
  fetch_detail incremental: hanya URL yang belum ada (dibandingkan dalam
  bentuk bersih — rtrim '/' + split '?' — karena sitemap menyimpan URL mentah
  sedangkan normalisasi menyimpan versi bersih; kalau dibandingkan mentah,
  semua URL dianggap baru → duplikat). normalisasi dedup URL bersih.
  Terverifikasi: run penuh exit 0 (13 menit), 4.787 berita, AppTest OK.
- indikator resmi per tema (nama + formula + satuan) dari hasil OCR PDF
  Kepmen (`docs/kepmen_361_ocr.txt`); tampil di expander dashboard + tabel
  laporan statis (14 tema)

## Caveat

- REST API wp-json diblokir (401) — tidak bisa dipakai; fetch halaman manual.
- Situs ugm.ac.id sering timeout; script sudah punya retry.
- Keyword slug bisa memunculkan false positive (mis. "usaha" di nama lembaga);
  daftar "tidak match" tersedia di dashboard untuk cek manual.
- Berita EN (ugm.ac.id/en) dan ID (ugm.ac.id/id) bisa duplikat konten
  (terjemahan). Dedup berdasarkan URL, bukan konten.
- Baseline sitemap = semua berita situs (32.130: /id/berita/ + /en/news/,
  ID/EN duplikat terjemahan); `berita` hanya subset yang slug-nya match
  keyword tema — proporsi di chart "Cakupan vs Total" indikasi kasar.
- Angka bertema adalah lower-bound: keyword terbatas pada 14 tema + deskripsi
  yang tersedia di halaman.

## Re-tagging keyword berbasis detailing tabel Kepmen (2026-08-21)

Semua keyword mapping (dampak/pilar, tema Kepmen, SDG) dirombak agar
bersumber dari detailing indikator tiap tema di TABEL Kepmen 361
(bagian "DEFINISI, KRITERIA, KETENTUAN, DAN FORMULA", OCR:
`docs/kepmen_361_ocr.txt`) — bukan dugaan/istilah umum. Prinsip:

1. Keyword = istilah yang benar-benar muncul di detailing tema itu
   (nama tema, definisi, kriteria, ketentuan). Istilah di luar detailing
   DIBUANG, mis.: ekosistem/habitat/wildlife/deforestasi (kehati),
   umkm/smes (kewirausahaan — itu tema Pengabdian/Pengeluaran Institusi),
   polusi/pencemaran/microplastic/biodegradable (limbah),
   regulasi (kebijakan publik), bangunan hijau/net zero/karbon/biodiesel/
   transisi energi (energi), bus kampus/shuttle/trans jogja/transportasi
   publik/kampus hijau (transportasi), studi banding/delegasi/guest lecture
   (kunjungan akademik), bazar/pasar/pemberdayaan umkm (belanja UMKM),
   riset untuk masyarakat/penelitian terapan/applied research/science for
   society (penelitian & inovasi sosial).
2. Keyword baru dari detailing yang masuk: reboisasi, lahan kritis, ruang
   terbuka hijau, erosi, banjir (kehati); hilirisasi, paten, lisensi, royalti,
   komersialisasi, HKI, prototipe (kolaborasi riset); wisuda, seminar,
   konferensi, simposium, lomba, festival, gathering alumni (kunjungan
   akademik); PLTS, mikrohidro, emisi, kendaraan listrik (energi); pupuk
   organik, ekonomi sirkular, IPAL, komposting (limbah); BUMDes, ketahanan
   pangan, digitalisasi desa (pengabdian); puskesmas, pemerintah desa,
   kelurahan (kebijakan publik).
3. Kata luas yang = materi lintas-tema TIDAK dipakai (93/160 match tema
   "Pendidikan & Penelitian" ternyata noise berita umum lewat kata
   pembangunan berkelanjutan/perubahan iklim/sustainability — dibuang;
   tersisa 8 berita matkul/modul/ESD).
4. Token pendek (≤5 huruf) otomatis word boundary di `tag_kepmen_all.py`
   (proven: "paten" substring-match "kabupaten" 190x → \bpaten\b 2x relevan).

Hasil re-tag (DuckDB, 2026-08-21): 3.084 baris url–tema / 2.369 berita unik
bertema (49,5%); pilar Lingkungan 1.105, Sosial 1.009, Ekonomi 700; tema
terbesar rehabilitasi_lingkungan 638, pengabdian_masyarakat 635, limbah 392,
kewirausahaan 303; SDG terbesar SDG 8 (1.050), 17 (1.021), 1 (838), 13 (759).

## Migrasi penuh DuckDB -> MySQL (2026-08-29)

`data/ugm_news.duckdb` dihapus dari alur kerja sepenuhnya. Sebelumnya
(03deb4b-43d2cda) pipeline masih menulis ke DuckDB lokal dengan `sync_mysql.py`
sebagai step sinkronisasi terakhir ke MySQL (dashboard sudah baca MySQL sejak
migrasi awal, tapi pipeline-nya sendiri masih DuckDB-first). Sekarang seluruh
9 script pipeline (`backfill_sitemap.py`, `ingest.py`, `fetch_detail.py`,
`normalisasi.py`, `process_nlp.py`, `tag_kepmen_all.py`, `tag_sdg_langsung.py`,
`backfill_deskripsi.py`, `laporan_static.py`) baca/tulis langsung ke MySQL
lewat `scripts/db.py`; `sync_mysql.py` dan dua script legacy yang sudah
superseded (`tag_kepmen_berita.py`, `tag_kepmen_lengkap.py`) dihapus.

Perubahan desain:
- Tabel dasar (`berita_sitemap`, `berita_berita`) diberi PRIMARY KEY pada
  `url` (sebelumnya TEXT tanpa PK, hasil `to_sql` awal) lewat
  `ensure_url_primary_key()` -- sekali jalan, idempoten.
- Penulisan baris-per-item pakai `upsert()` (INSERT ... ON DUPLICATE KEY
  UPDATE) per batch ~100 baris, bukan satu transaksi besar -- proses
  `fetch_detail.py` yang bisa jalan berjam-jam tidak kehilangan data kalau
  berhenti di tengah jalan.
- `normalisasi.py` (DELETE + INSERT ulang seluruh tabel) dibungkus SATU
  transaksi, bukan dua commit terpisah -- kalau gagal di tengah, rollback
  mengembalikan tabel ke kondisi sebelumnya, bukan tabel kosong.
- Semua baca/tulis MySQL dibungkus retry 3x (jeda 5 detik) via
  `with_retry()`; satu item/batch yang gagal total di-log dan dilewati,
  tidak menghentikan seluruh pipeline.
- Engine SQLAlchemy pakai `pool_pre_ping=True` + `pool_recycle=3600` di
  semua titik koneksi (pipeline, dashboard, generate_narasi_llm.py).

Diverifikasi (2026-08-29): seluruh step dijalankan satu per satu terhadap
MySQL produksi (`backfill_sitemap.py`, `ingest.py`, `fetch_detail.py` --
0 URL baru, sudah tercakup run sebelumnya --, `normalisasi.py`,
`process_nlp.py`, `tag_kepmen_all.py`, `tag_sdg_langsung.py`,
`backfill_deskripsi.py`, `laporan_static.py`) plus `update_mingguan.py`
end-to-end; semua exit 0, angka hasil konsisten dengan sebelum migrasi
(mis. tag_sdg_langsung.py: 48,8% URL bertanda SDG, sama seperti catatan
2026-08-21 di atas). Dua bug ditemukan & diperbaiki selama migrasi: (1)
variabel lokal bernama `t` di `tag_kepmen_all.py`/`tag_sdg_langsung.py`
men-shadow helper `db.t()` (UnboundLocalError); (2) `print()` karakter
non-ASCII (`>=`, dll.) crash di konsol Windows cp1252 -- di-fix global
lewat `sys.stdout.reconfigure(encoding="utf-8")` di `scripts/db.py`.

## Pengembangan dashboard (2026-08-20 — 14 tema / 3 pilar lengkap)

Sosial pilar sebelumnya kosong (3 tema inti = Ekonomi, 1 = Lingkungan).
Sekarang: tagging SEMUA berita ke 14 tema resmi Kepmen
via `tag_kepmen_all.py`; klaster SDG 10 tema lain diisi dari sheet "#Ref"
(sebelumnya kosong). Dashboard: filter tema & pilar berlaku ke 14 tema;
bagian baru "Ringkasan per pilar"; peta Kepmen + SDG mencakup semua tema;
expander eksplorasi lama diganti tabel 14 tema. Hasil: 1.181 berita unik
(Lingkungan 547, Sosial 473, Ekonomi 373). Laporan statis disinkronkan
(11 chart + tabel 14 tema). Verifikasi: AppTest default + filter pilar
Sosial tanpa exception; Streamlit HTTP 200.

## Pengembangan dashboard (2026-08-19)

Dashboard diperluas dari 5 bagian menjadi 12 (lihat DASHBOARD.md):
peta Tema Resmi Kepmen & klaster SDGs (bar per tema Kepmen + bar per SDG +
heatmap tema×SDG + tabel pemetaan resmi), heatmap tema×tahun, tren bulanan,
cakupan vs total berita UGM, breakdown keyword, multi-tema, word frequency,
filter global di sidebar; daftar berita kini menampilkan kolom Tema Kepmen &
SDG. Laporan statis disinkronkan (8 chart + word frequency).
Verifikasi: AppTest 3 skenario (default, 1 tema, rentang tahun) tanpa
exception; Streamlit HTTP 200.

Referensi resmi di folder `sumber/`:
- `sumber/Salinan_Kepmen_361_M_KEP_2025_Indikator_Dampak.pdf` — Kepmen asli
  (scan; hasil OCR: `docs/kepmen_361_ocr.txt`, via `scripts/ocr_kepmen.py`)
- `sumber/Buku_IKU_Diktisaintek_Berdampak_V1.pdf` — buku IKU (12 IKU, detail)
- `sumber/UGM Analytics.xlsx` — template pengumpulan data + sheet `#Ref` (pemetaan
  Dampak → Tema Kepmen → SDGs), sumber mapping `scripts/kepmen_sdg.py`
