# Arsitektur UGM Analytics — vNEXT (Subproyek: Kurikulum, KKN, Mahasiswa, Berita, Akreditasi)

Tipe dokumen: Arsitektur aplikasi eksisting (reverse engineering dari implementasi)
Sumber: repo `ugm-analytics` (main, commit `33823be`, **2026-09-19**) — kode pipeline,
dashboard Streamlit, MySQL (`berita_*`/`akreditasi_*`), frontend React (`web/`),
API FastAPI (`api/`), paket deploy terisolasi (`deploy/`), docs
Status: Lengkap utk layer Business/Data/Application/Technology; KKN & Mahasiswa = rencana (belum dibangun)

**Perubahan besar sejak 2026-09-01** (revisi ini):
1. **Subproyek akreditasi** (2026-09-06) — registry 49 item LED/LKPS, dashboard
   Streamlit, generator dokumen Word, login akreditasi (Fase A+B, 2026-09-18).
2. **berita-dampak jadi multipage** (2026-09-06) — `dashboard_berita_dampak.py`
   tinggal shell navigasi (78 baris) + `pages_app/`.
3. **Frontend React/Vite + API FastAPI + paket deploy terisolasi** (merge branch
   `dev.yayan`, 2026-09-19) — jalur publik baru yang TIDAK lewat Streamlit.
4. **Penyimpanan terbelah dua**: MySQL untuk pipeline/dashboard analis,
   **PostgreSQL** untuk API produksi.
5. `ugm_news.duckdb` dihapus dari repo (2026-09-19).

## 1. BUSINESS LAYER

### Visi Layanan

Mengukur dampak UGM terhadap masyarakat (sosial, ekonomi, lingkungan) berbasis
regulasi resmi: Kepmen 361/M/KEP/2025 (3 pilar + 14 tema + indikator ber-formula)
dan 17 SDGs. Lima sumber data: kurikulum matkul berkelanjutan (eLOK), berita
publikasi ugm.ac.id, dokumen akreditasi LED/LKPS (internal), KKN desa binaan
(rencana), mahasiswa afirmasi (rencana).

### Proses Bisnis per Subproyek

| Proses | matkul-sustainability | kkn-desa-binaan | mahasiswa-afirmasi | berita-dampak | akreditasi |
|---|---|---|---|---|---|
| Pengumpulan data mentah | ✅ scrape_elok.py (eLOK) | ⏳ rencana | ⏳ rencana | ✅ backfill_sitemap, ingest, fetch_detail (+ **fetch_backlog.py** — isi lengkap artikel) | ✅ registry_kebutuhan_data.py (49 item, transkripsi dokumen LED/LKPS) |
| Normalisasi & dedup | ✅ normalize_matkul.py | — | — | ✅ normalisasi.py (auto-passthrough kolom non-inti) | — (data manual, bukan hasil scrape) |
| Tagging dampak (Kepmen/SDG) | ✅ tag_kepmen_matkul, tag_sdg_matkul | — | — | ✅ process_nlp, tag_kepmen_all.py, tag_sdg_langsung.py + **tag_unit_kerja.py** (44 fakultas/sekolah/unit kerja) | — (tidak relevan; fokus kelengkapan dokumen) |
| Input data manual | — | — | — | — | ✅ dashboard_akreditasi.py → `akreditasi_data_manual` (skema long/EAV + `baris_ke`) |
| Pipeline data live (Fase 2) | — | — | — | — | ✅ pipeline_item_tersedia.py (5 item "tersedia"), pipeline_sinta.py (publikasi Scopus/SINTA 18 DTPR), pipeline_dcse_berita.py (arsip RSS dcse.fmipa.ugm.ac.id) |
| Ekstraksi dokumen (Fase 3) | — | — | — | — | ✅ ekstraksi_pattern.py (pattern-matching, tanpa AI, dicoba dulu) → fallback ekstraksi_akreditasi.py (LLM, per batch item registry); hasil = PREVIEW di `akreditasi_upload_ekstraksi`, user review dulu sebelum masuk data manual |
| Agregasi per unit/tahun | ✅ ringkasan fakultas/prodi/tahun/topik | — | — | ✅ ringkasan pilar/topik/sdg/tahun + berita_unit_kerja | ✅ akreditasi_item_tersedia (status per item), data_source_map.json (61 item + ringkasan status) |
| Dashboard interaktif | ✅ dashboard_matkul_kepmen.py, dashboard_matkul_sdg.py | — | — | ✅ dashboard multipage: beranda, dampak, dampak×SDGs, SDGs, akreditasi, admin, profil | ✅ dashboard_akreditasi.py |
| Laporan statis offline | ✅ laporan_matkul_kepmen.html | — | — | ✅ laporan_berita_dampak.html + laporan_word.py (docx) | ✅ generate_template.py (satu .docx gabungan LED+LKPS) |
| Frontend publik non-Streamlit | — | — | — | ✅ `web/` React+Vite → `api/` FastAPI (parity dengan Streamlit belum diverifikasi) | ✅ halaman `/akreditasi` (login + kelengkapan + upload) |
| Update berkala otomatis | — | — | — | ✅ cron Sabtu 06:00 + tombol dashboard (fetch_backlog.py manual/background) | — |

### Aktor

Analis dampak UGM (admin data) · Unit pengelola (fakultas/prodi/KKN) · Tim
penyusun akreditasi prodi · Pemangku kepentingan eksternal (Kepmen Diktisaintek,
DIKTI, LAM-INFOKOM) · Publik (laporan statis, frontend publik)

## 2. DATA LAYER

| Domain | matkul-sustainability | berita-dampak | akreditasi | KKN & Mahasiswa |
|---|---|---|---|---|
| Penyimpanan | CSV + DuckDB lokal (`data/`) | MySQL `ugm_analytics`, prefix `berita_` | MySQL `ugm_analytics`, prefix `akreditasi_` | belum ada |
| Isi | elok_matkul_mentah/bersih/kepmen/sdg.csv, ringkasan_fakultas/prodi/tahun/topik.csv | `berita_sitemap`, `berita_berita` (kolom `isi`/`kredit`/`fetch_gagal_count`), `berita_berita_kepmen_all`, `berita_berita_sdg_all`, `berita_sitemap_sdg`, `berita_unit_kerja`, `berita_narasi_cache`, ringkasan_* | `akreditasi_fakultas`, `akreditasi_prodi`, `akreditasi_item_tersedia`, `akreditasi_data_manual`(+`_arsip_pdf`), `akreditasi_users`, `akreditasi_sessions`, `akreditasi_login_attempts`, `akreditasi_upload_file`, `akreditasi_upload_ekstraksi`, `akreditasi_riwayat_generate`, `akreditasi_berita_dcse`, `akreditasi_publikasi_dosen` | — |

Total: **33 tabel** di `ugm_analytics` (20 `berita_*`, 13 `akreditasi_*`; tidak ada tabel lain — diverifikasi `SHOW TABLES` 2026-09-19).

**Angka kunci live (kueri langsung 2026-09-19 — bukan snapshot dokumen):**

| Metrik | Nilai |
|---|---|
| URL sitemap | 32.281 |
| Baris berita (`berita_berita`) | 32.228 |
| Isi lengkap terisi | 32.209 (99,94%) |
| Rentang tanggal berita | 2004-11-08 → 2026-09-15 |
| Pasangan url–tema Kepmen | 35.882 (19.829 url unik = 61,5%) |
| Pilar | Sosial 12.534 · Ekonomi 8.701 · Lingkungan 7.430 |
| Tema terbesar | pengabdian_masyarakat 7.405 · kunjungan_akademik 5.547 · instansi_publik 4.754 · penelitian_inovasi_sosial 3.834 · rehabilitasi_lingkungan 3.405 |
| SDG langsung (mode "SDGs saja") | 127.871 pasangan / 31.873 url unik |
| Unit kerja | 13.488 pasangan / 10.310 url unik |
| Akreditasi | 20 fakultas · 18 prodi (FMIPA) · 61 item di `data_source_map.json` (5 tersedia / 56 tidak tersedia: 41 kurang akses data + 15 perlu penyusunan manusia) · `akreditasi_item_tersedia` 198 baris · `akreditasi_publikasi_dosen` 151 · `akreditasi_berita_dcse` 200 · `akreditasi_upload_ekstraksi` 237 (preview) · `akreditasi_data_manual` 118 baris (14 item, diisi 2026-09-16 s/d 2026-09-18) · `akreditasi_data_manual_arsip_pdf` 2.292 (isi lama dari PDF, diarsipkan) · 2 user · 1 file terupload · 1 riwayat generate |

Referensi resmi (satu sumber kebenaran, folder `sumber/`): `sumber/UGM Analytics.xlsx`
(sheet "Konten UGM Berdampak" = 7 baris Dampak→Topik Resmi→Klaster SDGs→Indikator→Sumber Data;
sheet "#Ref" = pemetaan Dampak→Topik Kepmen→SDG sparse/merged),
`sumber/Salinan_Kepmen_361_M_KEP_2025_Indikator_Dampak.pdf` (scan, OCR →
`berita-dampak/docs/kepmen_361_ocr.txt`), `sumber/Buku_IKU_Diktisaintek_Berdampak_V1.pdf`
(12 IKU — tema sama dgn Kepmen: 14).
Daftar 44 fakultas/sekolah/unit kerja UGM: diberikan langsung oleh pemilik project,
disimpan di `berita-dampak/scripts/unit_kerja.py`. Cakupan akreditasi: 20 fakultas /
18 prodi (seluruhnya FMIPA), struktur kebutuhan data dari
`akreditasi/docs/Data_Requirements_LED_LKPS_MEI.md`, status sumber per item dari
`akreditasi/data_source_map.json` (61 item, snapshot 2026-09-11 — peta status yang
menentukan mana yang bisa dipenuhi pipeline live dan mana yang tidak). Catatan
penting: PDF LED/LKPS lama HANYA dipakai untuk menentukan struktur/kebutuhan item
(kode, nama, kriteria, tabel) — angka/isi dari PDF tidak dipindah; isi lama dari
tabel data manual sudah diarsipkan ke `akreditasi_data_manual_arsip_pdf`.

**Penyimpanan terbelah dua (penting):**
- Pipeline + dashboard Streamlit (analis) → **MySQL** `ugm_analytics` (`.env` root).
- API publik (`api/`) → **PostgreSQL 16** (`POSTGRES_*`, `api/app/db.py`). Nama tabel di
  query tetap `berita_*` karena datanya hasil kopi dari dump MySQL
  (`deploy/migrate_mysql_to_postgres.py`, dump di-import oleh service `mysql-reader`).
- `matkul-sustainability` → DuckDB/CSV lokal.
- `kkn-desa-binaan/` & `mahasiswa-afirmasi/`: `data/` + `scripts/` masih kosong.

## 3. APPLICATION LAYER

| Komponen | Teknologi | Bukti |
|---|---|---|
| Bahasa | Python 3.11 (venv `venv/` root) | pyproject/venv |
| Scraping (judul/deskripsi) | requests + bs4; retry wajib; fetch_detail parallel 8 thread + throttle | backfill_sitemap.py, fetch_detail.py |
| Scraping (isi lengkap) | BeautifulSoup selector `div.inner-content` (tervalidasi 17 sampel lintas 2008–2026, dua pola URL); fallback `<p>`/`<li>` → child `<div>` polos (template ~2010-2016); kredit redaksional dipisah ke kolom `kredit` | `fetch_backlog.py` — SUMBER TUNGGAL `fetch_full()`, `clean_url()`, `ensure_fetch_columns()`, di-*import* `fetch_detail.py`; JANGAN diduplikasi |
| Retry cap | kolom `fetch_gagal_count`, berhenti setelah 3x gagal (KECUALI baris yang belum pernah ada — artikel baru tidak dianggap gagal permanen) | `fetch_backlog.bump_fail_counts()`, `MAX_GAGAL` |
| OCR | pymupdf (dpi=200) + rapidocr-onnxruntime | ocr_kepmen.py → kepmen_361_ocr.txt |
| Normalisasi | pandas (strip teks, konversi tanggal, dedup URL mentah→bersih); auto-passthrough kolom di luar 6 kolom inti lewat `SHOW COLUMNS` | normalize_matkul.py, normalisasi.py |
| Tagging tema/SDG | keyword substring case-insensitive (judul+deskripsi+isi lengkap, ID+EN); token ≤5 huruf `\b..\b`; multi-tema by design; SDG dedup per url; fallback `db.column_exists()` | tag_kepmen_all.py, tag_sdg_langsung.py, process_nlp.py, tag_kepmen_matkul.py |
| Tagging unit kerja | substring nama resmi penuh (BUKAN singkatan) 44 fakultas/sekolah/unit kerja; guard leakage lintas-universitas; `kredit` dikecualikan | tag_unit_kerja.py, unit_kerja.py |
| Mapping resmi | `scripts/kepmen_sdg.py` — TOPIK_KEPMEN, TEMA_KEPMEN_LENGKAP, TOPIK_KEPMEN_ALL (14 tema), SDG_NAMA, WARNA_PILAR; `scripts/unit_kerja.py` | dipakai dashboard + tagging + laporan + API (via `api/app/domain/source.py`) |
| Narasi dinamis | template pandas (`narasi_logic.py`), opsional dirangkai ulang via **OpenAI API** (sebelumnya Gemini); tie-handling (kalau tema/SDG teratas seri, tampilkan SEMUA yang seri) | `_top_tied()`/`_join_labels()`, `generate_narasi_llm.py` |
| Dashboard analis | **Streamlit multipage**: `dashboard_berita_dampak.py` (shell) + `pages_app/` + `page_dampak.py` (1.459 baris), `page_sdgs.py`, `page_akreditasi.py`, `page_admin.py`, `page_profil.py`, `pencarian.py`, `data_loader.py`, `common.py`, `laporan_word.py` | port 8766 |
| Dashboard akreditasi | Streamlit: registry 49 item + form input manual (`st.data_editor`) + tombol generate docx | akreditasi/dashboard_akreditasi.py |
| Laporan statis | plotly `write_html` (JS inline, offline) — BUKAN matplotlib/kaleido | laporan_static.py → *.html |
| **API publik** | FastAPI + SQLAlchemy + psycopg; `/api/v1/analytics/*` (metadata, home-summary, search, impact, sdgs, news, reports, refresh-status) + `/accreditation/*` (auth register/login/me/logout, uploads) | `api/app/api/v1/analytics.py`, `api/app/services/` |
| **Frontend publik** | React 19 + Vite 7 + TypeScript + react-router-dom; SPA klien, grafik SVG/CSS sendiri (bukan plotly); state filter di URL (`year_from`, `pillars`, `topics`, `sdgs`, `units`) | `web/src/App.tsx`, `web/src/lib/api.ts` |
| **Deploy** | Compose terisolasi: postgres + mysql-reader + api + web + edge nginx (subpath `/analytics/`); Dockerfile `deploy/api.Dockerfile`, `deploy/web.Dockerfile` | `deploy/compose.yml`, `deploy/README.md` |
| Automasi update | update_mingguan.py + lock `data/.update_lock`; Popen detached dari tombol dashboard; `fetch_backlog.py` punya lock sendiri (`data/.fetch_backlog_lock`) | update_mingguan.sh |
| Auth akreditasi | registrasi + login email/password (bcrypt), **dibatasi domain UGM** (`ALLOWED_DOMAINS = {ugm.ac.id, mail.ugm.ac.id}`, dicocokkan persis setelah `@`), sesi cookie HttpOnly SameSite=strict 12 jam, tabel sessions + login_attempts, akun pertama otomatis admin | `api/app/services/accreditation_auth.py`, `akreditasi/scripts/auth_akreditasi.py` |
| Pipeline akreditasi live (Fase 2) | 3 pipeline: item "tersedia" (identitas PT/UPPS/PS, status akreditasi PS, VMTS, dll — snapshot replace), SINTA (10 publikasi Scopus terbaru per dosen, upsert akumulatif), RSS dcse.fmipa.ugm.ac.id (200 berita sebagai evidence) | pipeline_item_tersedia.py, pipeline_sinta.py, pipeline_dcse_berita.py |
| Ekstraksi dokumen akreditasi (Fase 3) | Dua tier: pattern-matching TANPA AI dulu (`ekstraksi_pattern.py`, untuk item berstruktur daftar berulang — lebih cepat, gratis, confidence pasti) → fallback LLM per batch item registry; hasil masuk `akreditasi_upload_ekstraksi` sebagai PREVIEW, user review & klik Simpan dulu | ekstraksi_pattern.py, ekstraksi_akreditasi.py, validasi_ekstraksi_pattern.py |
| Generator laporan akreditasi | DUA generator: `generate_template.py` (baca `akreditasi_data_manual`, section kosong tetap dibuat + placeholder "⚠️ Data belum tersedia") dan `generate_laporan_live.py` (Fase 3, sumber murni live hasil pipeline Fase 2, tidak menyentuh tabel data manual) | akreditasi/scripts/ |
| Render akreditasi bersama | Satu modul render dipakai dua entry point: dashboard akreditasi mandiri DAN menu "Akreditasi" di dashboard berita-dampak (`page_akreditasi.py`) — data yang diisi di salah satu muncul di lainnya (tabel MySQL yang sama) | akreditasi/scripts/dashboard_render.py |

### Lapisan akreditasi (Fase 1 → 3)

Akreditasi berkembang cepat dan TIDAK mengikuti pola scrape→tag subproyek lain:

```
Fase 1 — registry & peta status sumber
  registry_kebutuhan_data.py (49 item LED/LKPS, struktur dari dokumen requirement)
  data_source_map.json       (61 item: 5 tersedia / 41 tidak_tersedia_akses_data
                              / 15 tidak_tersedia_perlu_penyusunan_manusia)

Fase 2 — pipeline data live (mengisi yang "tersedia")
  pipeline_item_tersedia.py  → akreditasi_item_tersedia   (5 item, snapshot replace)
  pipeline_sinta.py          → akreditasi_publikasi_dosen (publikasi Scopus/SINTA)
  pipeline_dcse_berita.py    → akreditasi_berita_dcse     (arsip RSS, evidence)

Fase 3 — ekstraksi dokumen upload + generator laporan live
  upload_akreditasi.py       → akreditasi_upload_file (file fisik di data/uploads/<prodi>/)
  ekstraksi_pattern.py       (TANPA AI, dicoba dulu; utk daftar berulang)
       ↓ fallback
  ekstraksi_akreditasi.py    (LLM per batch item registry, gateway OpenAI-compatible
                              model "cx/gpt-5.6-luna"; response_format JSON strict
                              TIDAK ditegakkan model → parsing harus defensif)
       ↓
  akreditasi_upload_ekstraksi (PREVIEW — user review & klik Simpan baru masuk
                               akreditasi_data_manual)
       ↓
  generate_laporan_live.py   (docx dari data live) / generate_template.py (docx dari
                              akreditasi_data_manual, section kosong tetap dibuat)
```

Dua entry point UI berbagi satu modul render (`dashboard_render.py`): dashboard
akreditasi mandiri dan menu "Akreditasi" di dashboard berita-dampak. Data yang diisi
di salah satu langsung terlihat di lainnya karena tabel MySQL-nya sama.

Catatan operasional: API publik (`api/app/services/accreditation*.py`) hanya
mengimplementasikan subset (kelengkapan read-model, auth, upload) — ekstraksi AI,
pipeline live, dan admin user TIDAK ada di API, masih hanya di jalur Streamlit.
Uploads API disimpan ke `ACCREDITATION_UPLOAD_DIR` (di container: volume
`runtime/accreditation-uploads`), sedangkan jalur Streamlit menulis ke
`akreditasi/data/uploads/` — dua lokasi berbeda untuk deployment berbeda.

## 4. TECHNOLOGY LAYER

| Komponen | Detail |
|---|---|
| Sumber data kurikulum | elok.ugm.ac.id (Moodle, akses guest) — offline-first: butuh izin sebelum re-scrape |
| Sumber data berita | ugm.ac.id: sitemap `wp-sitemap.xml` (33 file), RSS `/id/feed/` + `/en/feed/` (10 item each); wp-json DIBLOKIR (401) |
| Database (pipeline/dashboard) | **MySQL** `ugm_analytics` — SQLAlchemy `pool_pre_ping=True` + `pool_recycle=3600`; upsert batch kecil + retry 3x; ringkasan full-replace |
| Database (API publik) | **PostgreSQL 16** (`deploy/compose.yml` service `postgres`, `postgres:16-alpine`) — diisi dari dump MySQL lewat `mysql-reader` + `migrate_mysql_to_postgres.py` |
| Database (matkul) | DuckDB file lokal — satu koneksi tulis mengunci TOTAL file di Windows → dashboard `read_only=True` + retry 10×1s |
| Serving analis | Streamlit port 8766, headless; LAN via firewall rule (`buka_akses_dashboard_admin.bat`); lintas jaringan via Tailscale |
| Serving publik | Nginx (edge + web) di dalam Compose, bind default `127.0.0.1` (`UGM_ANALYTICS_BIND_ADDRESS`), subpath `/analytics/` |
| Scheduling | Hermes cron `update_berita_dampak.sh` Sabtu 06:00 (`0 6 * * 6`); `fetch_backlog.py` TIDAK termasuk jadwal ini |
| Versioning | Git repo PRIVATE `putribloemhard-code/ugm-analytics` (auth `~/.git-credentials`; collaborator baca: dedieko-priyadi) |
| Tooling lokal | `node v24` + `npm 11` terpasang (tapi `web/node_modules` belum ada); **Docker TIDAK terpasang**; `mysql` CLI tidak ada di PATH; MySQL server lokal jalan di port 3306 |
| Referensi resmi | `sumber/UGM Analytics.xlsx`, `sumber/Salinan_Kepmen_361...pdf`, `sumber/Buku_IKU...pdf`; 44 unit kerja dari pemilik project |

## 5. TEMUAN KONSOLIDASI (operasional/arsitektur)

- ugm.ac.id wp-json diblokir 401 → sitemap + RSS adalah sumber sah; situs sering timeout → retry wajib
- eLOK: user menolak probing jaringan live — semua kerja berbasis data lokal; re-scrape harus konfirmasi dulu
- DuckDB di Windows: koneksi tulis mengunci file total — **HANYA berlaku `matkul-sustainability`** (berita-dampak & akreditasi sudah MySQL; `ugm_news.duckdb` dihapus 2026-09-19)
- **MySQL (pipeline) vs PostgreSQL (API) adalah dua database berbeda** — nama tabel di `api/app/services/analytics.py` tetap `berita_*` karena hasil kopi dump, BUKAN karena API menunjuk MySQL. Salah paham ini mudah terjadi saat membaca kode API berdampingan dengan `scripts/db.py`
- Keyword false-positive DITOLAK berbasis validasi sampel: delegation (prestasi lomba), desa/village, kebijakan/policy, nuclear (terlalu luas)
- Keyword WAJIB bersumber dari detailing tabel Kepmen (definisi/kriteria/ketentuan per tema, OCR `berita-dampak/docs/kepmen_361_ocr.txt`); kata luas lintas-tema ditolak; token ≤5 huruf otomatis word boundary (proven: "paten" → 190 FP "kabupaten" → `\bpaten\b` 2 match)
- Klaster SDG adalah atribut TEMA, bukan matching per berita; SDG di-dedup per url — **konsekuensi non-obvious**: tema dominan suatu unit bisa membawa SDG yang tak terkait isi teks artikelnya (contoh nyata Biro Transformasi Digital: 16/18 berita ke tema "Penelitian dan Inovasi" → otomatis SDG 1 & 9 [resmi Kepmen], padahal teksnya lebih ke SDG 9/17; di mode "SDGs saja" SDG 1 anjlok ke 1/19). Mode "Dampak × SDGs" dan "SDGs" TIDAK saling menggantikan
- Angka dampak = lower-bound keyword match — jangan jadikan angka dokumen sebagai kebenaran runtime; kueri DB. (Angka live 2026-09-19 ada di §2; snapshot historis 2026-09-01 di §7)
- Update mingguan menulis DB 10–15 mnt → dashboard tak bisa dibuka; lock file cegah update ganda
- PyMuPDF Windows menolak path MSYS `/d/...` — pakai `D:/...`
- **Isi lengkap artikel tidak selalu di `<p>`**: 265/274 baris kosong pasca-backfill ternyata template lama (~2010-2016) menaruh paragraf di `<div>` polos — selector cuma cari `<p>`/`<li>`. Pelajaran: validasi selector di sampel lintas tahun, jangan cuma sampel terbaru
- **Bug DELETE+INSERT tabel `berita_berita` (normalisasi.py) 2x menghapus kolom baru** (`isi`/`kredit`, lalu `fetch_gagal_count`) karena script rewrite total tabel dengan daftar kolom inti hardcoded. Fix permanen: auto-passthrough SEMUA kolom di luar 6 kolom inti lewat `SHOW COLUMNS`. Pelajaran: script yang "rewrite tabel penuh" jangan hardcode daftar kolom
- **Dashboard: filter turunan yang "mewarisi" filter lain secara implisit** — chart ranking unit awalnya ikut bias ke unit yang sedang dipilih; root cause bukan di titik pemakaian data (`selected_news`) tapi di variabel ANTARA (`t`) yang sudah ke-intersect lebih dulu. Pelajaran: kalau bikin "versi tanpa filter X", telusuri SEMUA variabel antara
- Filter sidebar yang cuma dirender di dalam blok `if/else` mode tertentu bisa hilang total di mode lain (widget "Fakultas / Unit Kerja" sempat hilang di mode "SDGs") — filter global sebaiknya dirender di luar percabangan mode
- Buku IKU (12 IKU) dan Kepmen 361 (3 pilar/14 tema) BERBAGI taksonomi tema yang sama — jangan campur hitungan: 12 IKU kinerja PT ≠ 14 tema indikator dampak
- **Lapisan web/api belum bisa dijalankan di mesin dev**: `web/node_modules` belum ada, Docker tidak terpasang, dan API butuh PostgreSQL yang belum ada lokal. Konsekuensi: perubahan `web/`/`api/` hanya bisa diverifikasi lewat `npm install` + Postgres lokal, atau lewat host BTD — jangan mengklaim "sudah jalan" tanpa salah satunya
- **Auth akreditasi dibatasi domain UGM** (diverifikasi di kode 2026-09-19): `ALLOWED_DOMAINS = {"ugm.ac.id", "mail.ugm.ac.id"}`, dicocokkan PERSIS pada bagian setelah `@` (bukan `endswith()` longgar) supaya `x@palsu-ugm.ac.id` / `x@ugm.ac.id.contoh.com` tertolak; password bcrypt; akun pertama otomatis admin; admin tidak bisa memblokir/menghapus/mencabut status admin akunnya sendiri. Yang MASIH belum ada (ditunda, lihat PRD): assignment role per prodi, audit log aksi akreditasi, dan cookie `Secure` (di API masih `secure=False` untuk dev/HTTP)
- **Ekstraksi dokumen: hasil = PREVIEW, bukan data final** — `akreditasi_upload_ekstraksi` menampung hasil (237 baris per 2026-09-19) dan user wajib review + klik Simpan sebelum masuk `akreditasi_data_manual`. Jangan pernah menganggap ekstraksi otomatis mengisi data resmi
- **Model LLM gateway tidak menegakkan JSON Schema strict** (`cx/gpt-5.6-luna` mengabaikan `response_format`, dicoba 2026-09-16) → parsing respons ekstraksi harus defensif. Tier pattern-matching (`ekstraksi_pattern.py`) sengaja dicoba DULU karena lebih cepat, gratis, dan confidence-nya pasti (bukan tebakan model)
- **PDF LED/LKPS lama hanya dipakai untuk struktur** (kode_item, nama, kriteria, tabel) — tidak ada angka/isi PDF yang dipindah; isi lama tabel data manual diarsipkan ke `akreditasi_data_manual_arsip_pdf` (2.292 baris), bukan dibuang
- **Dokumen arsitektur mudah tertinggal dari kode** (dokumen ini sendiri sempat 18 hari tertinggal): `docs/PERENCANAAN.md` masih 100% versi DuckDB/milestone 2026-08-20 sebelum disinkronkan 2026-09-19. Pelajaran: setiap merge fitur besar, perbarui PERENCANAAN + FRAMEWORK + ARCHITECTURE dalam commit yang sama

## 6. KARAKTER ARSITEKTUR

- Multi-sumber, satu makna: 2 sumber eksternal (eLOK, ugm.ac.id) + 3 referensi resmi dipetakan ke satu taksonomi (Kepmen 361 + SDG) lewat `kepmen_sdg.py`; berita-dampak tambahan: 1 sumber internal (44 fakultas/unit kerja dari pemilik project) lewat `unit_kerja.py` — lapisan independen, TIDAK menyentuh taksonomi Kepmen/SDG. API publik memuat modul Python yang SAMA (`api/app/domain/source.py`) supaya taksonomi tidak diduplikasi
- Pola pipeline seragam per subproyek: scrape → normalisasi → tagging → agregasi → output (dashboard + laporan); `fetch_backlog.py` (isi lengkap) adalah backfill terpisah dari siklus mingguan. `akreditasi/` menyimpang by design: registry → input manual → generate dokumen (tidak ada scraping)
- Output ganda: Streamlit interaktif (analis) + HTML plotly inline (berbagi offline) + **jalur ketiga** React/FastAPI (publik, belum di-deploy)
- Data lokal-first namun terpusat per subproyek: MySQL self-hosted untuk pipeline (bukan lagi file lokal), PostgreSQL untuk API; keduanya render offline, tanpa layanan eksternal runtime saat serving
- Bottom-up: data mentah → tag → agregasi → pilar/SDG → laporan; setiap lapisan bisa diverifikasi manual
- Fail-safe by default: kolom/fitur baru selalu punya jalur fallback aman (`db.column_exists()` sebelum scan `isi`; `fetch_gagal_count` berhenti otomatis; narasi LLM skip aman ke template pandas; `api/app/api/v1/analytics.py` mengembalikan 503 dengan pesan client-safe alih-alih traceback)
- Migrasi bertahap dengan rollback terjaga: Streamlit tetap baseline sampai parity React terverifikasi (PRD), MySQL tetap jadi sumber tulis sampai Postgres terbukti, dan akreditasi sengaja ditahan di Streamlit sampai RBAC/audit/sesi dirancang

## 7. DOKUMEN TERKAIT

- `docs/PERENCANAAN.md` (tujuan/backlog/milestone/status per subproyek) · `docs/FRAMEWORK.md` (arsitektur/konvensi/stack) · `berita-dampak/docs/OUTPUT.md` (hasil) · `docs/listing-ide-analisis-dampak.md` (ide backlog) · `docs/PRD_FRONTEND_NON_STREAMLIT.md` (PRD migrasi Streamlit→React/FastAPI) · `docs/HANDOVER_DEPLOYMENT_REPORT_UGM_ANALYTICS_20260828.pdf` (laporan handover deployment) · `berita-dampak/docs/kepmen_361_ocr.txt` (OCR Kepmen)
- Per subproyek: `README.md` (peta file) + `PIPELINE.md` (alur) + `DASHBOARD.md` (isi dashboard) — matkul-sustainability, berita-dampak, akreditasi lengkap
- Referensi resmi: `sumber/UGM Analytics.xlsx` · `sumber/Salinan_Kepmen_361_M_KEP_2025_Indikator_Dampak.pdf` · `sumber/Buku_IKU_Diktisaintek_Berdampak_V1.pdf`
- **Angka kunci live (2026-09-19, kueri langsung MySQL)** — lihat tabel di §2. Ringkas: 32.228 berita, 19.829 bertema (61,5%), isi lengkap 99,94%, SDG langsung 31.873 url, unit kerja 10.310 url, akreditasi 18 prodi FMIPA.
- Angka kunci historis (2026-09-01, sebelum frontend/API, basis 32.191 berita): tema Kepmen 19.800 unik (61,5%); pilar Sosial 12.514 / Ekonomi 8.688 / Lingkungan 7.411; topik terbesar pengabdian_masyarakat 7.391, kunjungan_akademik 5.544; SDG terbesar (mode Berdampak × SDGs) SDG 8 (12.888), 11 (12.224), 17 (11.197), 1 (10.253); SDG langsung 31.873/32.194 (99,0%); unit kerja 10.296/32.191 (32,0%)
- Angka kunci historis (2026-08-21, DuckDB, sebelum migrasi MySQL & isi lengkap — basis 4.787 berita): 2.369 unik bertopik (49,5%); pilar Lingkungan 1.105 / Sosial 1.009 / Ekonomi 700; SDG terbesar SDG 8 (1.050), 17 (1.021). Matkul: 382 matkul bersih, 23 terkait sustainability (6,0%), Kehutanan 10/17 (58,8%) — matkul-sustainability tidak berubah sejak 2026-08-12
