# OUTPUT — Apa yang Dihasilkan (berita-dampak)

Terakhir disinkronkan: **2026-09-19**. Angka di dokumen ini = snapshot; verifikasi
runtime selalu dari MySQL live (lihat "Cara query manual" di bawah).

## 1. Tampilan interaktif (web)

Tampilan interaktif: web React + API (`web/`, `api/`), dijalankan lokal dengan `jalankan_web_baru.bat` di root repo → http://127.0.0.1:3000/dampak. Dashboard Streamlit dihapus 2026-09-23 (riwayat di git).

Bagian yang dulu ada di dashboard Streamlit (ringkasan, distribusi per tema, peta tema × SDG,
tren, cakupan, keyword, multi-tema, word frequency, daftar berita, unit kerja) kini dirender dari
`GET /api/v1/analytics/story` (`api/app/services/story.py`). Narasi LLM (`berita_narasi_cache`)
dipakai hanya saat filter default (label "dirangkai AI"); selain itu narasi template `narasi_logic.py`.

## 2. Laporan statis HTML (offline)

File: `berita-dampak/laporan_berita_dampak.html` (plotly JS inline — buka langsung
di browser tanpa server/internet). Regenerate:

```bash
..\venv\Scripts\python.exe scripts\laporan_static.py
```

Isi: chart + tabel indikator resmi 14 tema + tabel contoh berita per tema.

Ada juga laporan Word dari web: tombol "Unduh laporan" → `POST /api/v1/analytics/reports`
(`api/app/services/report.py`).

## 3. Database MySQL

Database: MySQL `ugm_analytics` (kredensial `.env` root repo), semua tabel berprefix
`berita_`. Migrasi penuh dari DuckDB selesai 2026-08-29; file `data/ugm_news.duckdb`
sudah DIHAPUS dari repo (2026-09-19).

Skema inti `berita_berita`: `url`, `judul`, `tanggal`, `deskripsi`, `kategori`,
`sumber`, `isi` (isi lengkap artikel), `kredit` (byline redaksional, SENGAJA tidak
ikut keyword matching), `fetch_gagal_count` (cap 3x).

| Tabel | Isi | Snapshot 2026-09-19 |
|---|---|---|
| `berita_sitemap` | URL berita ugm.ac.id + lastmod (baseline) | 32.281 |
| `berita_berita` | Judul, tanggal, deskripsi, isi lengkap, kredit | 32.228 (isi terisi 32.209 = 99,94%) |
| `berita_berita_kepmen_all` | url–topik–dampak–topik_kepmen–sdg (14 tema resmi, sumber utama) | 35.882 baris / 19.829 url unik (61,5%) |
| `berita_berita_sdg_all` | url–sdg (dedup) | — |
| `berita_berita_topik` | url–tema (4 tema inti, legacy proses lama) | — |
| `berita_ringkasan_topik_all` | jumlah berita unik per tema (SELALU 14 baris, zero-fill) | 14 |
| `berita_ringkasan_pilar` | jumlah berita per pilar | 3 (Sosial 12.534, Ekonomi 8.701, Lingkungan 7.430) |
| `berita_ringkasan_pilar_tahun` | jumlah berita per pilar per tahun | — |
| `berita_ringkasan_sdg_all` | jumlah berita per SDG (warisan tema) | 14 |
| `berita_sitemap_sdg` | url–sdg mapping LANGSUNG seluruh sitemap (mode "SDGs saja") | 127.871 pasangan / 31.873 url unik |
| `berita_ringkasan_sdg_sitemap(_tahun)` | jumlah url unik per SDG (17 SDG) | 17 |
| `berita_unit_kerja` | url–unit–kategori (44 fakultas/sekolah/unit kerja UGM) | 13.488 pasangan / 10.310 url unik |
| `berita_narasi_cache` | cache narasi LLM (cache_key, narasi, generated_at) | — |
| `berita_berita_kepmen`, `berita_berita_sdg`, `berita_ringkasan_sdg` | legacy (4 tema inti, tidak dipakai dashboard) | — |
| `berita_berita_kepmen_lengkap`, `berita_ringkasan_kepmen_lengkap` | legacy (eksplorasi 9 tema) | — |

Cara query manual: `mysql` CLI TIDAK ada di PATH mesin dev — pakai Python:

```bash
cd D:\ugm-analytics
./venv/Scripts/python.exe -c "
import os; from dotenv import load_dotenv; load_dotenv()
import pandas as pd; from sqlalchemy import create_engine, text
e = create_engine(f\"mysql+pymysql://{os.getenv('MYSQL_USER')}:{os.getenv('MYSQL_PASSWORD')}@{os.getenv('MYSQL_HOST')}:{os.getenv('MYSQL_PORT','3306')}/{os.getenv('MYSQL_DB')}\")
print(pd.read_sql(text('SELECT COUNT(*) FROM berita_berita'), e))
"
```

Tidak ada masalah kunci-file seperti DuckDB, jadi query baca aman saat dashboard
jalan. Hindari perintah tulis saat update pipeline sedang berjalan.

## 4. Angka kunci

**Live 2026-09-19** (kueri langsung MySQL): 32.228 berita · 19.829 bertema dampak
(61,5%) · pilar Sosial 12.534 / Ekonomi 8.701 / Lingkungan 7.430 · tema terbesar
pengabdian_masyarakat 7.405, kunjungan_akademik 5.547, instansi_publik 4.754,
penelitian_inovasi_sosial 3.834, rehabilitasi_lingkungan 3.405 · SDG langsung
31.873 url · unit kerja 10.310 url · rentang tanggal 2004-11-08 → 2026-09-15.

Snapshot historis (2026-08-21, DuckDB, basis 4.787 berita — JANGAN dipakai sebagai
angka sekarang): bertema dampak 2.369 (49,5%); pilar Lingkungan 1.105, Sosial 1.009,
Ekonomi 700; tema terbesar rehabilitasi_lingkungan 638, pengabdian_masyarakat 635,
limbah 392; SDG terbesar SDG 8 (1.050), 17 (1.021), 1 (838).

Semua angka bertema adalah **lower-bound** keyword match, bukan angka resmi.

## 5. Update otomatis

- **Cron Hermes**: Sabtu 06:00 (`0 6 * * 6`), job `update_berita_dampak.sh` →
  `scripts/update_mingguan.py`. Log: `logs_update.txt` / `logs_update_mingguan.txt`.
- **Tombol web**: `/admin` → "Update data" (khusus admin; log `logs_update_dashboard.txt`).
- Manual: `..\venv\Scripts\python.exe scripts\update_mingguan.py`.
- `update_mingguan.py` menjalankan pipeline berurutan; lock `data/.update_lock`
  mencegah tabrakan; fetch incremental (hanya URL baru/belum ada isinya).
- **`fetch_backlog.py` TIDAK termasuk jadwal mingguan** — backfill isi lengkap
  dijalankan manual/background, punya lock sendiri `data/.fetch_backlog_lock`
  dan mengecek lock update_mingguan supaya tidak bentrok.

## 6. Jalur output ketiga: frontend React + API (belum aktif)

Sejak 2026-09-19 repo juga punya `web/` (React+Vite) + `api/` (FastAPI) + `deploy/`
(Compose terisolasi) yang menyajikan analitik publik TANPA Streamlit. API membaca
PostgreSQL (bukan MySQL lokal). Belum dijalankan di mesin dev (Docker tidak
terpasang, `web/node_modules` belum ada) — lihat `docs/FRAMEWORK.md` dan
`docs/PRD_FRONTEND_NON_STREAMLIT.md`.
