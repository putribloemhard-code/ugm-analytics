# FRAMEWORK — Arsitektur & Konvensi UGM Impact Analytics

Terakhir disinkronkan: **2026-09-19**.

## Stack

| Lapisan | Teknologi |
|---|---|
| Bahasa | Python 3.11 (venv `venv/` di root workspace) |
| Data — berita-dampak & akreditasi | **MySQL** `ugm_analytics` (kredensial `.env` root repo; prefix tabel `berita_` / `akreditasi_`) |
| Data — matkul-sustainability | CSV + DuckDB lokal di `matkul-sustainability/data/` (belum dimigrasi) |
| Data — API produksi | **PostgreSQL 16** (`api/app/db.py`, env `POSTGRES_*`) — tabel `berita_*` dikopi dari MySQL |
| Pustaka pipeline | pandas, plotly, streamlit, requests, bs4, openpyxl, pymupdf, rapidocr-onnxruntime, sqlalchemy, pymysql, python-dotenv, openai |
| Pustaka API | fastapi, uvicorn, sqlalchemy, psycopg[binary], pymysql, pandas, python-docx, bcrypt, python-multipart |
| Frontend | React 19 + Vite 7 + TypeScript + react-router-dom (grafik SVG/CSS sendiri, bukan plotly) |
| Output statis | plotly `write_html` (JS inline — render tanpa internet). BUKAN matplotlib/kaleido |
| Serving | Streamlit port 8766 (analis, LAN/Tailscale) · React+Nginx (publik, via Compose) |
| Scheduling | Hermes cron `update_berita_dampak.sh` → `update_mingguan.py` (Sabtu 06:00) |
| Container | `deploy/compose.yml` (postgres + mysql-reader + api + web + edge). Docker belum terpasang di mesin dev |
| OS | Windows; terminal git-bash (MSYS) |

## Peta repo

```
ugm-analytics/
├── berita-dampak/        # analisis berita dampak (pipeline + multipage dashboard + laporan)
├── akreditasi/           # registry LED/LKPS + dashboard + generator dokumen Word
├── matkul-sustainability/# analisis matkul sustainability (CSV/DuckDB lokal)
├── kkn-desa-binaan/      # kosong (butuh data eLOK)
├── mahasiswa-afirmasi/   # kosong (data sensitif)
├── web/                  # frontend React + Vite (SPA)
├── api/                  # FastAPI read-only + layanan akreditasi
├── deploy/               # paket deploy terisolasi (Compose, Dockerfile, nginx, migrasi)
├── shared/               # aset & style bersama lintas dashboard Streamlit
├── sumber/               # referensi resmi (xlsx template Kepmen, PDF Kepmen, Buku IKU)
└── docs/                 # dokumen lintas proyek
```

## Pola folder per subproyek

```
<subproyek>/
├── README.md          # peta file + cara menjalankan
├── PIPELINE.md        # alur processing + perintah run + hasil + caveat
├── DASHBOARD.md       # isi dashboard + cara membaca hasil
├── dashboard_<nama>.py  # Streamlit interaktif
├── laporan_<nama>.html  # laporan statis (plotly inline, offline)
├── data/              # CSV/DuckDB lokal, atau kosong kalau MySQL-only
├── scripts/           # pipeline: scrape → normalize → tag → aggregate → report
└── docs/              # dokumen & sumber KHUSUS subproyek ini
```

Dokumen/sumber yang dipakai ≥2 subproyek TIDAK masuk `<subproyek>/docs/` — tetap di
root `docs/` (dokumen) atau root `sumber/` (data/PDF/xlsx sumber). Contoh:
`sumber/UGM Analytics.xlsx` dipakai `berita-dampak/` maupun `matkul-sustainability/`.

## Pipeline berita-dampak (detail)

Seluruh tabel di MySQL (prefix `berita_`, lihat `berita-dampak/scripts/db.py`).

```
backfill_sitemap.py → berita_sitemap (URL + lastmod dari ugm.ac.id/wp-sitemap.xml)
ingest.py           → RSS /id/feed/ + /en/feed/ → berita_berita (sumber='rss')
fetch_detail.py     → filter URL sitemap relevan + fetch halaman (8 thread, throttle)
                      → berita_berita (sumber='sitemap'), isi/kredit via fetch_backlog.fetch_full()
fetch_backlog.py    → backfill BESAR isi lengkap seluruh sitemap (manual/background,
                      BUKAN bagian STEPS mingguan) + kolom kredit + fetch_gagal_count
normalisasi.py      → bersihkan teks, konversi tanggal, dedup URL (mentah→bersih),
                      auto-passthrough kolom non-inti
process_nlp.py      → tagging 4 tema inti → berita_berita_topik, berita_ringkasan_topik_tahun
tag_kepmen_all.py   → tagging 14 tema Kepmen + SDG → berita_berita_kepmen_all,
                      berita_berita_sdg_all, berita_ringkasan_pilar(_tahun), berita_ringkasan_sdg_all,
                      berita_ringkasan_topik_all
tag_sdg_langsung.py → mode "SDGs saja" → berita_sitemap_sdg, berita_ringkasan_sdg_sitemap(_tahun)
tag_unit_kerja.py   → 44 fakultas/sekolah/unit kerja → berita_unit_kerja
generate_narasi_llm.py → narasi via OpenAI API → berita_narasi_cache (opsional, skip aman)
laporan_static.py   → laporan_berita_dampak.html
update_mingguan.py  → jalankan seluruh pipeline berurutan (lock data/.update_lock;
                      dipakai cron + tombol dashboard)
```

Penulisan baris-per-item (sitemap, berita) pakai `upsert()` (INSERT ... ON
DUPLICATE KEY UPDATE) per batch kecil + retry 3x. Tabel ringkasan/agregat
full-replace (`to_sql(if_exists="replace")`).

## Mapping resmi (satu sumber kebenaran)

- `berita-dampak/scripts/kepmen_sdg.py` — `TOPIK_KEPMEN` (4 tema inti),
  `TEMA_KEPMEN_LENGKAP` (10 tema lain), `TOPIK_KEPMEN_ALL` (14 tema),
  `LABEL_TOPIC_ALL`, `WARNA_PILAR`, `SDG_NAMA`. Dashboard Streamlit, script
  tagging, dan laporan statis semua import dari sini.
- `berita-dampak/scripts/unit_kerja.py` — 44 fakultas/sekolah/unit kerja UGM
  (nama resmi penuh; TANPA singkatan) + guard leakage lintas-universitas.
- `api/app/domain/source.py` — jembatan untuk API: memuat modul Python yang
  sama (`kepmen_sdg.py`, `narasi_logic.py`, `unit_kerja.py`) supaya taksonomi
  tidak diduplikasi di sisi API.
- Sumber: `sumber/UGM Analytics.xlsx` sheet "Konten UGM Berdampak" (7 baris resmi)
  + "#Ref" (Dampak→Tema→SDG, sparse/merged — baca per-sel dengan koordinat),
  PDF Kepmen 361 (OCR: `berita-dampak/docs/kepmen_361_ocr.txt`).
- Pitfall konseptual: klaster SDG adalah atribut TEMA (semua berita dalam satu
  tema membawa SDG sama), bukan hasil matching per berita. Konsekuensinya mode
  "Dampak × SDGs" dan mode "SDGs saja" menjawab pertanyaan berbeda dan tidak
  bisa saling menggantikan.

## Konvensi tagging

- Substring match case-insensitive pada judul + deskripsi + **isi lengkap**
  (kalau kolomnya ada, lewat `db.column_exists()`); ID + EN.
- Kolom `kredit` (byline redaksional) SENGAJA dikecualikan dari matching —
  byline bisa salah men-tag unit yang cuma menerbitkan, bukan yang dibahas.
- Berita bisa multi-tema (multi-tag by design); SDG di-dedup per url.
- Token pendek (≤5 huruf) otomatis word boundary di `tag_kepmen_all.py`
  (proven: "paten" substring-match "kabupaten" 190x → `\bpaten\b` 2x relevan).
- Keyword dipilih berbasis bukti: simulasi jumlah match + validasi sampel judul.
  Kandidat false-positive DITOLAK (delegation, desa/village, kebijakan/policy,
  nuclear) — catatan di `berita-dampak/PIPELINE.md`.
- Selalu sediakan daftar "tidak match" di dashboard untuk cek manual.

## Lapisan aplikasi baru (web + api + deploy)

```
Browser (React SPA, web/)
   │  JSON / unduhan .docx
   ▼
FastAPI (api/, prefix /api/v1)
   │  query read-only + layanan akreditasi
   ▼
PostgreSQL 16 (deploy/compose.yml: service postgres)
   ▲
mysql-reader (mysql:8.0) ← impor analytics.reader.sql saat init
```

- Endpoint publik: `/healthz`, `/api/v1/analytics/{metadata,home-summary,search,
  impact,sdgs,news,reports,refresh-status}`.
- Endpoint akreditasi: `/api/v1/analytics/accreditation{,/auth/register,/auth/login,
  /auth/me,/auth/logout,/uploads}` — cookie sesi `HttpOnly` + `SameSite=strict`,
  `max_age=43200` (12 jam, `SESSION_AGE = timedelta(hours=12)`), dan `secure=False`
  (dev/HTTP — WAJIB diubah saat produksi HTTPS).
- Frontend route: `/`, `/dampak`, `/dampak-sdgs`, `/sdgs`, `/akreditasi`.
- Deploy memakai **subpath** `/analytics/`: `VITE_APP_BASE_PATH=/analytics/`,
  `VITE_API_BASE_URL=/analytics/api/v1` (edge nginx mem-proxy `/api/` ke FastAPI).
- **Catatan penting**: `api/` membaca **PostgreSQL**, bukan MySQL, walau nama
  tabel di query tetap `berita_*`. Jangan mengarahkan API ke MySQL lokal tanpa
  menyesuaikan `api/app/db.py`.
- Streamlit TETAP jadi baseline rollback selama parity React belum diverifikasi
  (lihat `docs/PRD_FRONTEND_NON_STREAMLIT.md`).

## Pipeline akreditasi (registry + peta status → data live → ekstraksi → generate)

```
Fase 1  scripts/registry_kebutuhan_data.py  → 49 item data (dict KEBUTUHAN_DATA), statis
        data_source_map.json                → 61 item: 5 tersedia / 41 tidak_tersedia_akses_data
                                              / 15 tidak_tersedia_perlu_penyusunan_manusia
        scripts/migrasi_tabel_*.py          → CREATE TABLE IF NOT EXISTS (idempoten)

Fase 2  pipeline_item_tersedia.py           → akreditasi_item_tersedia (5 item, snapshot replace)
        pipeline_sinta.py                   → akreditasi_publikasi_dosen (publikasi Scopus/SINTA)
        pipeline_dcse_berita.py             → akreditasi_berita_dcse (arsip RSS, evidence)

Fase 3  upload_akreditasi.py                → akreditasi_upload_file + file di data/uploads/<prodi>/
        ekstraksi_pattern.py                → tier 1: TANPA AI (struktur tabel/pola teks berulang)
        ekstraksi_akreditasi.py             → tier 2: LLM per batch item registry
        akreditasi_upload_ekstraksi         → PREVIEW; user review & klik Simpan dulu
        akreditasi_data_manual              → skema long/EAV (+ kolom baris_ke)

Output  generate_template.py                → .docx dari akreditasi_data_manual
        generate_laporan_live.py            → .docx dari data live hasil Fase 2
        dashboard_render.py                 → dipakai dashboard akreditasi mandiri
                                              DAN menu "Akreditasi" berita-dampak
```

Section/tabel yang datanya belum ada TETAP dibuat (header lengkap) dan ditandai
placeholder italic — dokumen selalu jadi template lengkap, bukan bolong-bolong.
Skema koneksi: `pool_pre_ping=True` + `pool_recycle=3600` + retry 3x (adaptasi
`berita-dampak/scripts/db.py`, prefix `akreditasi_`).
Login akreditasi dibatasi domain UGM (`ugm.ac.id`, `mail.ugm.ac.id`, dicocokkan
persis setelah `@`), password bcrypt, akun pertama otomatis admin.

## Koneksi MySQL — aturan penting

- Engine SQLAlchemy WAJIB `pool_pre_ping=True` + `pool_recycle=3600` (lihat
  `berita-dampak/scripts/db.py::get_engine()`) — tanpa ini, proses panjang
  (`fetch_detail.py` bisa jalan berjam-jam) crash dengan "MySQL server has gone away".
- Penulisan baris-per-item WAJIB upsert per batch kecil (~100 baris), bukan satu
  transaksi raksasa. Tabel dasar (`berita_sitemap`, `berita_berita`) punya PRIMARY
  KEY pada `url` untuk ini.
- Semua baca/tulis dibungkus retry 3x (`db.with_retry()` / `db.read_sql_retry()`);
  satu item/batch yang gagal total di-log dan DILEWATI, tidak menghentikan pipeline.
- Tabel ringkasan/agregat (hitung ulang total tiap run) full-replace.
- Jangan pakai nama variabel `t` di script yang juga `import db` — `db.t()` adalah
  helper prefix tabel; variabel lokal bernama sama men-shadow-nya (bug nyata 2026-08-29).
- `mysql` CLI TIDAK ada di PATH mesin dev. Query manual lewat Python:
  `venv/Scripts/python.exe` + `load_dotenv()` + SQLAlchemy (`SHOW TABLES`, `pd.read_sql`).
- Jangan menjalankan perintah tulis (INSERT/UPDATE/DELETE/DROP) saat update pipeline
  berjalan; query baca aman (tidak ada kunci-file seperti DuckDB).

## DuckDB di Windows — aturan penting

**Hanya berlaku untuk `matkul-sustainability/`** (satu-satunya subproyek yang masih
pakai DuckDB lokal). `berita-dampak` dan `akreditasi` sudah MySQL.

- Satu koneksi tulis mengunci file TOTAL; dashboard harus `read_only=True` dengan
  retry 10×1s.
- Query manual: `duckdb -readonly data/<nama_file>.duckdb`. DBeaver: pakai wizard
  koneksi DuckDB (File → New → Database Connection), JANGAN File → Open (menampilkan
  sampah biner).
- Tidak ada file `.duckdb` yang di-track di repo (`ugm_news.duckdb` dihapus 2026-09-19).

## Jaringan & akses

- ugm.ac.id: wp-json diblokir (401); sitemap + RSS adalah sumber sah;
  situs sering timeout → retry wajib di semua fetch.
- Dashboard Streamlit dari laptop lain: firewall rule port 8766
  (`berita-dampak/buka_akses_dashboard_admin.bat`, cetak IP IPv4 aktif), atau Tailscale untuk
  lintas jaringan. IP LAN bisa berubah — cek `ipconfig` dulu, jangan hardcode.
- Laporan HTML statis bisa dikirim tanpa server (render offline).
- Frontend React: `web/vite.config.ts` dev server 127.0.0.1:3000; build statis
  di-serve nginx (subpath `/analytics/`).
