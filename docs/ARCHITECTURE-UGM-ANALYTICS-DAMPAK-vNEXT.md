# Arsitektur UGM Analytics — Dampak vNEXT (4 Subproyek: Kurikulum, KKN, Mahasiswa, Berita)

Tipe dokumen: Arsitektur aplikasi eksisting (reverse engineering dari implementasi)
Sumber: repo `ugm-analytics` (main, 2026-09-01) — kode pipeline, dashboard, MySQL (berita-dampak) / DuckDB (matkul-sustainability), docs
Status: Lengkap utk layer Business/Data/Application/Technology; KKN & Mahasiswa = rencana (belum dibangun)

**Perubahan besar sejak 2026-08-21** (berita-dampak saja — matkul-sustainability/KKN/mahasiswa
tidak berubah): migrasi penuh DuckDB → MySQL (2026-08-29); ekstraksi ISI LENGKAP artikel
(bukan cuma judul+deskripsi pendek dari meta tag) untuk seluruh 32.191 berita, dengan kredit
redaksional dipisah ke kolom sendiri; lapisan tagging baru independen — 44 fakultas/sekolah/unit
kerja UGM; filter "Fakultas / Unit Kerja" + tab baru di dashboard; beberapa bug non-trivial
ditemukan & diperbaiki (lihat §5).

## 1. BUSINESS LAYER

### Visi Layanan

Mengukur dampak UGM terhadap masyarakat (sosial, ekonomi, lingkungan) berbasis
regulasi resmi: Kepmen 361/M/KEP/2025 (3 pilar + tema + indikator ber-formula) dan
17 SDGs. Empat sumber data: kurikulum matkul berkelanjutan (eLOK), berita publikasi
ugm.ac.id, KKN desa binaan (rencana), mahasiswa afirmasi (rencana).

### Proses Bisnis per Subproyek

| Proses | matkul-sustainability | kkn-desa-binaan | mahasiswa-afirmasi | berita-dampak |
|---|---|---|---|---|
| Pengumpulan data mentah | ✅ scrape_elok.py (eLOK) | ⏳ rencana | ⏳ rencana | ✅ backfill_sitemap, ingest, fetch_detail (+ **fetch_backlog.py** — isi lengkap artikel, bukan cuma judul/deskripsi) |
| Normalisasi & dedup | ✅ normalize_matkul.py | — | — | ✅ normalisasi.py (digeneralisasi 2026-09-01 — auto-passthrough kolom apa pun di luar 6 kolom inti, lihat §5) |
| Tagging dampak (Kepmen/SDG) | ✅ tag_kepmen_matkul, tag_sdg_matkul | — | — | ✅ process_nlp, tag_kepmen_all.py, tag_sdg_langsung.py + **tag_unit_kerja.py** (lapisan baru, independen — 44 fakultas/sekolah/unit kerja UGM) |
| Agregasi per unit/tahun | ✅ ringkasan fakultas/prodi/tahun/topik | — | — | ✅ ringkasan pilar/topik/sdg/tahun + berita_unit_kerja |
| Dashboard interaktif | ✅ dashboard_matkul_kepmen.py, dashboard_matkul_sdg.py | — | — | ✅ dashboard_berita_dampak.py (+ filter "Fakultas / Unit Kerja" di 3 mode, tab "Fakultas/Unit Kerja" per pilar) |
| Laporan statis offline | ✅ laporan_matkul_kepmen.html | — | — | ✅ laporan_berita_dampak.html |
| Update berkala otomatis | — | — | — | ✅ cron Sabtu 06:00 + tombol dashboard (fetch_backlog.py backfill isi lengkap DI LUAR jadwal ini — dijalankan manual/background) |

### Aktor

Analis dampak UGM (admin data) · Unit pengelola (fakultas/prodi/KKN) ·
Pemangku kepentingan eksternal (Kepmen Diktisaintek, DIKTI) · Publik (laporan statis)

## 2. DATA LAYER

| Domain | matkul-sustainability | berita-dampak | KKN & Mahasiswa |
|---|---|---|---|
| Kurikulum | elok_matkul_mentah/bersih/kepmen/sdg.csv, ringkasan_fakultas.csv (21), ringkasan_prodi.csv, ringkasan_tahun.csv, ringkasan_topik.csv | — | — |
| Berita | — | `berita_sitemap` (32.194 URL), `berita_berita` (32.191 baris — **isi lengkap terisi di 32.190/32.191, 99,997%**, kolom `isi`/`kredit`/`fetch_gagal_count`), `berita_berita_kepmen_all` (35.811 pasangan, 19.800 berita unik match ≥1 tema = 61,5%), `berita_berita_sdg_all`, `berita_sitemap_sdg` (31.873 URL unik bertanda ≥1 SDG = 99,0%, mode "SDGs saja"), **`berita_unit_kerja`** (BARU — 13.470 pasangan url-unit, 10.296 berita unik = 32,0% match ≥1 dari 44 fakultas/sekolah/unit kerja), ringkasan_pilar/topik/sdg/_tahun | — |

Referensi resmi (satu sumber kebenaran, folder `sumber/`): `sumber/UGM Analytics.xlsx`
(sheet "Konten UGM Berdampak" = 7 baris Dampak→Topik Resmi→Klaster SDGs→Indikator→Sumber Data;
sheet "#Ref" = pemetaan Dampak→Topik Kepmen→SDG sparse/merged),
`sumber/Salinan_Kepmen_361_M_KEP_2025_Indikator_Dampak.pdf` (scan, OCR →
`docs/kepmen_361_ocr.txt`), `sumber/Buku_IKU_Diktisaintek_Berdampak_V1.pdf` (12 IKU — tema sama dgn Kepmen: 14).
Daftar 44 fakultas/sekolah/unit kerja UGM: diberikan langsung oleh pemilik project (bukan hasil
scraping), disimpan di `berita-dampak/scripts/unit_kerja.py`.

Penyimpanan: **berita-dampak migrasi penuh ke MySQL** (2026-08-29, database `ugm_analytics`,
tabel prefix `berita_`, kredensial `.env` root repo) — DuckDB (`data/ugm_news.duckdb`) TIDAK
dipakai lagi untuk subproyek ini. matkul-sustainability MASIH pakai DuckDB (CSV di `data/`,
caveat koneksi-tulis-mengunci-file di §5 & §6 HANYA berlaku untuk subproyek ini sekarang). KKN
& mahasiswa: `data/` + `scripts/` masih kosong.

## 3. APPLICATION LAYER

| Komponen | Teknologi | Bukti |
|---|---|---|
| Bahasa | Python 3.11 (venv `venv/` root) | pyproject/venv |
| Scraping (judul/deskripsi) | requests + bs4; retry wajib; fetch_detail parallel 8 thread + throttle | backfill_sitemap.py, fetch_detail.py |
| **Scraping (isi lengkap)** | **BeautifulSoup selector `div.inner-content`** (tervalidasi manual 17 sampel lintas 2008–2026, dua pola URL); fallback 2 tingkat — `<p>`/`<li>` dulu, baru child `<div>` polos kalau tidak ada `<p>` (template artikel lama ~2010-2016an); baris kredit redaksional ("Penulis:"/"Author:"/dst.) dipisah dari isi ke kolom `kredit`, safe-default kalau pola tak jelas (semua tetap masuk `isi`) | `fetch_backlog.py` — SUMBER TUNGGAL fungsi ekstraksi (`fetch_full()`, `clean_url()`, `ensure_fetch_columns()`), di-*import* langsung oleh `fetch_detail.py`, JANGAN diduplikasi |
| Retry cap | kolom `fetch_gagal_count`, berhenti coba ulang otomatis setelah 3x gagal berturut-turut (KECUALI baris yang belum pernah ada sama sekali — supaya artikel baru tidak dianggap gagal permanen di percobaan pertama) | `fetch_backlog.bump_fail_counts()`, `MAX_GAGAL` |
| OCR | pymupdf (render dpi=200) + rapidocr-onnxruntime | ocr_kepmen.py → kepmen_361_ocr.txt |
| Normalisasi | pandas (strip teks, konversi tanggal, dedup URL mentah→bersih); berita-dampak: **auto-passthrough kolom apa pun di luar 6 kolom inti** lewat `SHOW COLUMNS` (generalisasi 2026-09-01, lihat §5) | normalize_matkul.py, normalisasi.py |
| Tagging tema/SDG | keyword substring case-insensitive (judul+deskripsi**+isi lengkap kalau ada**, ID+EN); token pendek pakai `\b..\b`; multi-topik by design; SDG dedup per url; fallback aman lewat `db.column_exists()` kalau kolom `isi` belum ada | tag_kepmen_all.py, tag_sdg_langsung.py, process_nlp.py, tag_kepmen_matkul.py |
| **Tagging unit kerja** | substring match nama resmi penuh (BUKAN singkatan — risiko false-positive tinggi, lihat §5) 44 fakultas/sekolah/unit kerja; guard leakage lintas-universitas (skip occurrence yang diikuti "Universitas \<nama lain\>"); `kredit` SENGAJA dikecualikan dari matching | `tag_unit_kerja.py`, `scripts/unit_kerja.py` |
| Mapping resmi | modul `scripts/kepmen_sdg.py` — satu sumber kebenaran: TOPIK_KEPMEN, TEMA_KEPMEN_LENGKAP, TOPIK_KEPMEN_ALL (14 tema), SDG_NAMA, WARNA_PILAR | dipakai dashboard + tagging + laporan |
| Narasi dinamis | template pandas (`narasi_logic.py`), opsional dirangkai ulang via Gemini API; **tie-handling** — kalau tema/SDG teratas seri (nilai sama persis), tampilkan SEMUA yang seri, bukan pilih satu sembarang | `_top_tied()`/`_join_labels()`, dipakai `generate_executive_summary`/`generate_impact_insight`/`generate_sdg_saja_summary` |
| Dashboard | Streamlit (filter sidebar global — tahun/tema/pilar/SDG/**Fakultas-Unit Kerja di ketiga mode**, 11 bagian berita + tab "Fakultas/Unit Kerja" per pilar / drill-down fakultas-prodi matkul) | dashboard_berita_dampak.py |
| Laporan statis | plotly `write_html` (JS inline, offline) — BUKAN matplotlib/kaleido | laporan_static.py → *.html |
| Automasi update | update_mingguan.py + lock `data/.update_lock`; Popen detached dari tombol dashboard; **`fetch_backlog.py` PUNYA lock sendiri** (`data/.fetch_backlog_lock`) + cek lock update_mingguan supaya tidak bentrok, TAPI TIDAK termasuk STEPS mingguan (backfill isi lengkap besar dijalankan manual/background) | update_mingguan.sh |

## 4. TECHNOLOGY LAYER

| Komponen | Detail |
|---|---|
| Sumber data kurikulum | elok.ugm.ac.id (Moodle, akses guest) — offline-first: butuh izin sebelum re-scrape |
| Sumber data berita | ugm.ac.id: sitemap `wp-sitemap.xml` (33 file), RSS `/id/feed/` + `/en/feed/` (10 item each); wp-json DIBLOKIR (401) |
| Database (berita-dampak) | **MySQL** (database `ugm_analytics`, tabel prefix `berita_`, migrasi penuh 2026-08-29) — `SQLAlchemy` engine WAJIB `pool_pre_ping=True` + `pool_recycle=3600` (proses panjang seperti fetch_backlog.py bisa jalan berjam-jam); upsert per batch kecil (`ON DUPLICATE KEY UPDATE`) + retry 3x; tabel ringkasan/agregat full-replace tiap run |
| Database (matkul-sustainability) | DuckDB file lokal — satu koneksi tulis mengunci TOTAL file di Windows → dashboard wajib `read_only=True` + retry 10×1s; query manual `duckdb -readonly` (caveat ini TIDAK berlaku lagi utk berita-dampak) |
| Serving dashboard | Streamlit port 8766, headless; LAN via firewall rule (`buka_akses_dashboard_admin.bat`); lintas jaringan via Tailscale |
| Scheduling | Hermes cron `update_berita_dampak.sh` Sabtu 06:00 (backfill isi lengkap `fetch_backlog.py` TIDAK termasuk jadwal ini — manual/background) |
| Versioning | Git repo PRIVATE `putribloemhard-code/ugm-analytics` (auth `~/.git-credentials`; collaborator baca: dedieko-priyadi) |
| Referensi resmi | `sumber/UGM Analytics.xlsx`, `sumber/Salinan_Kepmen_361...pdf`, `sumber/Buku_IKU...pdf`; daftar 44 fakultas/sekolah/unit kerja UGM diberikan langsung pemilik project |

## 5. TEMUAN KONSOLIDASI (operasional/arsitektur)

- ugm.ac.id wp-json diblokir 401 → reverse engineering: sitemap + RSS adalah sumber sah; situs sering timeout → retry wajib di semua fetch
- eLOK: user menolak probing jaringan live — semua kerja berbasis data lokal; re-scrape harus konfirmasi dulu
- DuckDB di Windows: koneksi tulis (DuckDB CLI / DBeaver wizard) mengunci file total — dashboard IOException; fix: `duckdb -readonly`, disconnect DBeaver, atau retry loop (**HANYA berlaku matkul-sustainability** — berita-dampak sudah migrasi ke MySQL 2026-08-29, lihat caveat "Koneksi MySQL" di `berita-dampak/PIPELINE.md`)
- Keyword false-positive DITOLAK berbasis validasi sampel: delegation (prestasi lomba), desa/village, kebijakan/policy, nuclear (terlalu luas)
- Keyword WAJIB bersumber dari detailing tabel Kepmen (definisi/kriteria/ketentuan per tema, OCR docs/kepmen_361_ocr.txt) — istilah di luar detailing dibuang; kata luas lintas-tema ditolak; token ≤5 huruf otomatis word boundary di tag_kepmen_all.py (proven 2026-08-21: "paten" substring-match "kabupaten" 190 FP → \bpaten\b 2 match relevan)
- Klaster SDG adalah atribut TOPIK (semua berita satu topik membawa SDG sama), bukan matching per berita; SDG di-dedup per url — **konsekuensi non-obvious** (ditemukan 2026-09-01 lewat pertanyaan user "kenapa SDG 1 menang, bukan SDG 17"): tema Kepmen dominan suatu unit BISA membawa SDG yang tidak terkait langsung ke isi tekstual artikelnya (contoh nyata: Biro Transformasi Digital 16/18 berita ke tema "Penelitian dan Inovasi" → otomatis SDG 1 & 9 [resmi Kepmen], padahal isi teksnya lebih ke SDG 9/17; giliran dicek di mode "SDGs" [keyword langsung ke teks, independen dari tema] SDG 1 anjlok ke 1/19, SDG 9 & 4 malah seri di 19, SDG 17 di 16) — mode "Berdampak × SDGs" dan mode "SDGs" TIDAK bisa dianggap saling menggantikan, keduanya jawab pertanyaan berbeda
- Angka dampak = lower-bound keyword match — **update 2026-09-01 (basis penuh 32.191 berita, isi lengkap ikut di-scan)**: tema Kepmen 19.800/32.191 (61,5%, naik dari 2.369/4.787=49,5% baseline 2026-08-21 sebagian besar karena isi lengkap + basis lebih besar), SDG langsung (mode "SDGs saja") 31.873/32.194 (99,0%, naik drastis dari sebelumnya keyword-di-slug-saja) — sediakan expander "tidak match" untuk cek manual
- Update mingguan menulis DB 10–15 mnt → dashboard tak bisa dibuka; lock file cegah update ganda
- PyMuPDF Windows menolak path MSYS `/d/...` — pakai `D:/...`
- **Isi lengkap artikel tidak selalu di `<p>`**: ~265/274 baris yang sempat kosong pasca-backfill (2026-09-01) ternyata bukan gagal fetch — template artikel lama (~2010-2016an) taruh tiap paragraf di `<div>` polos, bukan `<p>`; selector cuma cari `<p>`/`<li>` jadi kontennya ADA tapi tak ke-ambil. Fix: fallback ambil child `<div>` langsung kalau tidak ada `<p>` — pelajaran: validasi selector di sampel yang BENAR-BENAR beragam rentang tahun, jangan cuma sampel terbaru
- **Bug DELETE+INSERT tabel `berita_berita` (normalisasi.py) 2x menghapus kolom baru**: pertama kolom `isi`/`kredit`, lalu (setelah ditambal manual) kolom `fetch_gagal_count` lagi — script itu rewrite total tabel tiap run tapi cuma bawa daftar kolom inti yang di-hardcode. Fix permanen (bukan tambal per-kolom lagi): auto-*passthrough* SEMUA kolom di luar 6 kolom inti lewat `SHOW COLUMNS` — pelajaran: kalau ada script yang "rewrite tabel penuh" (DELETE+INSERT / full-replace), jangan hardcode daftar kolom, appear-once bugs berulang kalau kolom baru ditambah script lain di kemudian hari
- **Dashboard: filter turunan yang "mewarisi" filter lain secara implisit**: chart ranking unit di tab "Fakultas/Unit Kerja" awalnya ikut bias ke unit yang SEDANG dipilih di filter sidebar (co-occurrence di dalam subset dirinya sendiri) — root cause BUKAN di titik pemakaian data (variabel `selected_news`), tapi di variabel ANTARA (`t`, dari mana `selected_t` diturunkan) yang sudah ke-intersect ke url unit-filtered lebih dulu; perbaikan pertama (ganti basis `selected_news` doang) ternyata TIDAK cukup — harus ditelusuri ke variabel upstream-nya juga. Pelajaran: kalau mau bikin "versi tanpa filter X" dari suatu turunan data, telusuri SEMUA variabel antara yang membentuknya, bukan cuma titik pemakaian akhir
- Filter sidebar yang cuma dirender di dalam blok `if/else` mode tertentu bisa hilang total di mode lain tanpa disadari (widget "Fakultas / Unit Kerja" sempat cuma ada di mode "Berdampak"/"Berdampak × SDGs", hilang total di mode "SDGs" karena beda jalur kode/tabel sumber) — filter global sebaiknya dirender di luar percabangan mode, diterapkan terpisah per jalur data
- Buku IKU (12 IKU) dan Kepmen 361 (3 pilar/14 tema) BERBAGI taksonomi tema yang sama (Sosial 4, Ekonomi 5, Lingkungan 5) — rangkuman Kepmen menjabarkan tiap tema ke indikator+formula; jangan campur hitungan: 12 IKU kinerja PT ≠ 14 tema indikator dampak

## 6. KARAKTER ARSITEKTUR

- Multi-sumber, satu makna: 2 sumber eksternal (eLOK, ugm.ac.id) + 3 referensi resmi dipetakan ke satu taksonomi (Kepmen 361 + SDG) lewat `kepmen_sdg.py`; berita-dampak tambahan: 1 sumber internal (daftar 44 fakultas/unit kerja dari pemilik project) dipetakan lewat `unit_kerja.py` — lapisan independen, TIDAK menyentuh taksonomi Kepmen/SDG
- Pola pipeline seragam per subproyek: scrape → normalisasi → tagging → agregasi → output (dashboard + laporan), didokumentasikan README/PIPELINE/DASHBOARD; berita-dampak: scrape isi lengkap (fetch_backlog.py) adalah proses BACKFILL terpisah dari siklus mingguan reguler, bukan langkah tambahan di tengah pipeline
- Output ganda: Streamlit interaktif (analisis) + HTML plotly inline (berbagi offline tanpa server)
- Data lokal-first namun terpusat per subproyek: matkul-sustainability = DuckDB/CSV lokal; berita-dampak = MySQL self-hosted (bukan lagi file lokal per proses, migrasi 2026-08-29) — sama-sama render offline, tanpa layanan eksternal runtime saat serving dashboard
- Bottom-up: data mentah → tag → agregasi → pilar/SDG → laporan; setiap lapisan bisa diverifikasi manual
- Fail-safe by default: kolom/fitur baru yang ditambahkan (isi/kredit/fetch_gagal_count, tagging unit kerja) SELALU punya jalur fallback aman kalau prasyaratnya belum terpenuhi (`db.column_exists()` sebelum scan kolom `isi`; kandidat fetch berhenti otomatis, bukan retry selamanya, tapi TIDAK untuk baris yang belum pernah ada) — pola yang konsisten dipakai ulang di semua penambahan fitur sejak 2026-09-01

## 7. DOKUMEN TERKAIT

- `docs/PERENCANAAN.md` (tujuan/backlog/milestone) · `docs/FRAMEWORK.md` (arsitektur/konvensi/stack) · `docs/OUTPUT.md` (hasil) · `docs/listing-ide-analisis-dampak.md` (ide backlog) · `docs/kepmen_361_ocr.txt` (OCR Kepmen)
- Per subproyek: `README.md` (peta file) + `PIPELINE.md` (alur) + `DASHBOARD.md` (isi dashboard) — matkul-sustainability & berita-dampak lengkap
- Referensi resmi: `sumber/UGM Analytics.xlsx` · `sumber/Salinan_Kepmen_361_M_KEP_2025_Indikator_Dampak.pdf` · `sumber/Buku_IKU_Diktisaintek_Berdampak_V1.pdf`
- Angka kunci live berita-dampak (**2026-09-01, MySQL, basis penuh 32.191 berita — isi lengkap ikut discan**): tema Kepmen 19.800 unik bertopik (61,5%); pilar Sosial 12.514 / Ekonomi 8.688 / Lingkungan 7.411; topik terbesar pengabdian_masyarakat 7.391, kunjungan_akademik 5.544, instansi_publik 4.746, penelitian_inovasi_sosial 3.826, rehabilitasi_lingkungan 3.396; SDG terbesar (mode Berdampak × SDGs, warisan tema) SDG 8 (12.888), 11 (12.224), 17 (11.197), 1 (10.253); SDG langsung dari teks (mode "SDGs saja") 31.873/32.194 URL (99,0%). Unit kerja (BARU): 10.296/32.191 berita (32,0%) match ≥1 dari 44 fakultas/sekolah/unit kerja.
- Angka kunci historis (2026-08-21, DuckDB, sebelum migrasi MySQL & isi lengkap — basis 4.787 berita): 2.369 unik bertopik (49,5%); pilar Lingkungan 1.105 / Sosial 1.009 / Ekonomi 700; topik terbesar rehabilitasi_lingkungan 638, pengabdian_masyarakat 635, limbah 392, kewirausahaan 303; SDG terbesar SDG 8 (1.050), 17 (1.021), 1 (838), 13 (759). Matkul: 460 matkul, 21 fakultas, 5 topik sustainability (26 matkul tagged; Kehutanan 58.8%) — matkul-sustainability tidak berubah sejak tanggal ini.
