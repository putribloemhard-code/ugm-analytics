# UGM Impact Analytics

Analisis dampak UGM berdasarkan Kepmendikti Saintek **361/M/KEP/2025**
(Indikator Dampak Sosial, Ekonomi, dan Lingkungan Perguruan Tinggi) dan
klaster **SDGs** — berbasis data publik yang bisa diambil offline.

Terakhir disinkronkan: **2026-09-19**.

## Subproyek

| Subproyek | Fokus | Status |
|---|---|---|
| `berita-dampak/` | Analisis berita dampak ugm.ac.id (14 tema Kepmen, 3 pilar, SDG, 44 unit kerja) | **Aktif** — pipeline + multipage dashboard + laporan + update mingguan |
| `akreditasi/` | Kelengkapan data LED & LKPS (LAM-INFOKOM) | **Aktif** — registry 49 item + peta status 61 item + 3 pipeline data live + ekstraksi dokumen (pattern & AI) + dashboard + generator Word + login domain UGM |
| `matkul-sustainability/` | Mata kuliah terkait sustainability per fakultas/prodi | Selesai (2026-08-12) |
| `web/` + `api/` + `deploy/` | Frontend publik React/Vite + API FastAPI + paket deploy terisolasi | **Aktif** — dashboard satu-halaman (Dampak / Dampak × SDGs / SDGs), portal Akreditasi + login, Profil Saya & Admin; `jalankan_web_baru.bat` untuk pratinjau MySQL lokal |
| `kkn-desa-binaan/` | Sebaran KKN & desa binaan (data dari eLOK — belum ada) | Kosong, butuh akses eLOK |
| `mahasiswa-afirmasi/` | Analisis kelompok afirmasi (data sensitif — belum ada) | Kosong, butuh akses resmi |

## Mulai cepat

**berita-dampak (dashboard analis, Streamlit):**

```bash
cd D:\ugm-analytics\berita-dampak
..\venv\Scripts\streamlit run dashboard_berita_dampak.py     # buka http://localhost:8766
..\venv\Scripts\python.exe scripts\laporan_static.py          # regenerate laporan HTML
..\venv\Scripts\python.exe scripts\update_mingguan.py         # update data dari ugm.ac.id
```

Laporan statis (tanpa server): `berita-dampak/laporan_berita_dampak.html`.

Akses dari laptop lain: jalankan `buka_akses_dashboard_admin.bat` (butuh admin —
memasang firewall rule + mencetak IP LAN aktif). IP LAN bisa berubah, jadi jangan
hardcode; untuk lintas jaringan pakai Tailscale.

**akreditasi:**

```bash
cd D:\ugm-analytics\akreditasi
..\venv\Scripts\streamlit run dashboard_akreditasi.py
```

**frontend + API (jalur publik):**

```bash
# Pratinjau lokal (MySQL yang sama dengan dashboard Streamlit) — cukup klik dua kali:
jalankan_web_baru.bat                 # API :8000 + web :3000 (http://127.0.0.1:3000)

# Manual:
cd D:\ugm-analytics\web
npm ci && npm run dev                 # http://127.0.0.1:3000 (butuh API jalan)
# API memakai MySQL lokal: ..\.venv\Scripts\python.exe dev_api_mysql.py
# API produksi: cd api && uvicorn app.main:app --reload  (butuh PostgreSQL, env POSTGRES_*)
```

Catatan: ada DUA venv — `venv\` (pandas/plotly/streamlit, untuk subproyek Streamlit) dan
`.venv\` (fastapi/uvicorn/pytest, untuk `api/` dan `jalankan_web_baru.bat`). Jangan tertukar.

Deploy terisolasi (Compose: postgres + mysql-reader + api + web + edge nginx,
subpath `/analytics/`) — lihat `deploy/README.md`; butuh Docker (belum terpasang
di mesin dev).

## Peta folder tingkat atas

| Folder | Isi |
|---|---|
| `berita-dampak/` · `akreditasi/` · `matkul-sustainability/` | Subproyek (lihat tabel di atas) |
| `web/` · `api/` · `deploy/` | Lapisan aplikasi publik (React/Vite + FastAPI + Compose) |
| `shared/` | **Dipakai bersama lintas subproyek**: `style.py` (CSS global Streamlit — penyamarataan tinggi kartu via flexbox, diverifikasi lewat DOM Streamlit 1.61.1: `stColumn` bukan `column`), `assets/logo/` (logo UGM + ikon tiap halaman), `siapkan_logo.py` |
| `docs/` | Dokumen tingkat workspace (PERENCANAAN, FRAMEWORK, ARCHITECTURE, PRD, listing ide) |
| `sumber/` | Referensi resmi: `UGM Analytics.xlsx`, Kepmen 361 (PDF scan), Buku IKU (PDF) |
| `graphify-out/` | Output analisis graf kode (graph.html/json + GRAPH_REPORT.md) — **gitignored**, artefak lokal |
| `venv/` | Virtualenv Python 3.11 proyek |
| `kkn-desa-binaan/` · `mahasiswa-afirmasi/` | Subproyek kosong (menunggu akses data) |

## Dokumentasi

- `docs/PERENCANAAN.md` — tujuan, prinsip, backlog ide, milestone, status per subproyek
- `docs/FRAMEWORK.md` — stack, peta repo, pipeline, konvensi, aturan MySQL/DuckDB
- `docs/ARCHITECTURE-UGM-ANALYTICS-DAMPAK-vNEXT.md` — arsitektur lengkap per layer + temuan operasional
- `docs/PRD_FRONTEND_NON_STREAMLIT.md` — PRD migrasi Streamlit → React/Vite + FastAPI
- `docs/REVIEW_WEB_BARU_2026-09-21.md` — review dashboard web baru (temuan + perbaikan yang sudah dikerjakan)
- `docs/listing-ide-analisis-dampak.md` — ide backlog
- `berita-dampak/README.md` + `PIPELINE.md` + `DASHBOARD.md` + `docs/OUTPUT.md` — subproyek berita-dampak
- `akreditasi/README.md` + `PIPELINE.md` + `DASHBOARD.md` — subproyek akreditasi
- `matkul-sustainability/README.md` + `PIPELINE.md` + `DASHBOARD.md` — subproyek matkul
- `deploy/README.md` — paket deploy terisolasi (batas, kontrak env, gate pra-deploy)

## Referensi resmi (folder `sumber/`)

- `sumber/UGM Analytics.xlsx` — template resmi pengumpulan data Kepmen 361
  (sheet "Konten UGM Berdampak" = 7 baris template; sheet "#Ref" = pemetaan
  Dampak → Topik Kepmen → SDGs). SUMBER KEBENARAN mapping topik→Kepmen→SDG.
- `sumber/Salinan_Kepmen_361_M_KEP_2025_Indikator_Dampak.pdf` — Kepmen asli (scan;
  OCR: `berita-dampak/docs/kepmen_361_ocr.txt`)
- `sumber/Buku_IKU_Diktisaintek_Berdampak_V1.pdf` — 12 IKU (14 tema sama dgn Kepmen; jangan campur hitungan: 12 IKU ≠ 14 tema)

## Lingkungan

- Python venv: `venv/` (pandas, plotly, streamlit, requests, bs4, duckdb,
  openpyxl, pymupdf, rapidocr-onnxruntime, sqlalchemy, pymysql, python-dotenv,
  openai). Bukan matplotlib/kaleido — output statis pakai plotly `write_html`.
- Penyimpanan: **MySQL** `ugm_analytics` (berita-dampak + akreditasi; kredensial
  `.env` root, contoh di `.env.example`). `matkul-sustainability` masih CSV/DuckDB
  lokal. API publik membaca **PostgreSQL** (env `POSTGRES_*`).
- `mysql` CLI tidak ada di PATH mesin dev — query manual pakai Python + SQLAlchemy
  (contoh di `berita-dampak/docs/OUTPUT.md`).
- Node: `node v24` + `npm 11` terpasang (untuk `web/`). Docker belum terpasang.
- OS: Windows; terminal pakai git-bash (MSYS).
