# UGM Impact Analytics

Analisis dampak UGM berdasarkan Kepmendikti Saintek **361/M/KEP/2025**
(Indikator Dampak Sosial, Ekonomi, dan Lingkungan Perguruan Tinggi) dan
klaster **SDGs** — berbasis data publik yang bisa diambil offline.

Terakhir disinkronkan: **2026-09-21** (termasuk perapian struktur: file sisa dihapus, dump
database & legacy dipindah — lihat "Struktur & kepemilikan sumber" di bawah).

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

Akses dari laptop lain: jalankan `berita-dampak\buka_akses_dashboard_admin.bat` (butuh admin —
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
| `web/` · `api/` | Lapisan aplikasi publik (React/Vite + FastAPI) |
| `deploy/` | Paket deploy terisolasi (Compose + Dockerfile + nginx). `deploy/legacy/` = file lama yang sudah tidak dipakai jalur aktif (compose MySQL-only, skrip migrasi DuckDB→MySQL, README deploy Streamlit) — disimpan untuk jejak, bukan untuk dijalankan |
| `shared/` | **Dipakai bersama lintas subproyek**: `style.py` (CSS global Streamlit — penyamarataan tinggi kartu via flexbox, diverifikasi lewat DOM Streamlit 1.61.1: `stColumn` bukan `column`), `assets/logo/` (logo UGM + ikon tiap halaman), `siapkan_logo.py` |
| `docs/` | Dokumen tingkat workspace (PERENCANAAN, FRAMEWORK, ARCHITECTURE, PRD, listing ide) |
| `sumber/` | Referensi resmi (sharing, TIDAK boleh dihapus): `UGM Analytics.xlsx`, Kepmen 361 (PDF scan), Buku IKU (PDF), `picture/` (gambar mentah) |
| `venv/` · `.venv/` | Virtualenv Python (lihat catatan dua venv di atas) |
| `kkn-desa-binaan/` · `mahasiswa-afirmasi/` | Subproyek kosong (menunggu akses data) — hanya `.gitkeep` di `data/` + `scripts/` |

## Struktur & kepemilikan sumber (aturan 2026-09-21)

Aturan yang dipakai setelah perapian struktur:

1. **Sumber sharing** ada di dalam repo, di folder bersama: `sumber/` (dokumen & gambar mentah
   resmi), `shared/` (kode + aset Streamlit bersama), `web/public/` (aset web publik).
2. **Sumber per use case** ada di dalam folder use case masing-masing: `berita-dampak/`,
   `akreditasi/`, `matkul-sustainability/` — termasuk skrip, data, dashboard, dan dokumen.
3. **Duplikasi aset yang disengaja** (jangan "dirapikan" tanpa alasan):
   - logo: `sumber/picture/` (mentah) → `shared/assets/logo/` (Streamlit) → `web/public/logo/`
     (React). Isi `shared/assets/logo/` dan `web/public/logo/` IDENTIK (terverifikasi md5);
     `sumber/picture/` resolusinya beda (mentah). Yang dipakai kode: `shared/` + `web/public/`.
   - `hero_bg.jpg`: `berita-dampak/static/` (Streamlit, static serving) + `web/public/`
     (React). Isinya identik (md5) — dua app, dua folder aset, memang harus begitu.
4. **Ketergantungan runtime API → skrip subproyek** (sengaja, jangan dipindah):
   `api/app/domain/source.py` memuat modul dari `berita-dampak/scripts/` (`kepmen_sdg.py`,
   `unit_kerja.py`, `keywords.py`, `narasi_logic.py`, `sdg_keywords.py`) dan
   `akreditasi/scripts/`. Memindahkan file itu akan mematahkan `/analytics/story`.
5. **Dump database & secret TIDAK disimpan di repo** — lihat "Arsip di luar repo" di bawah.

## Tata letak laporan dampak di web (2026-09-23)

Bagian "Analisis Dampak" (`/dampak`, scene `dampak`) menampilkan blok **Laporan dampak per bab**
yang tata letaknya mengikuti daftar isi resmi
`sumber/LAPORAN DAMPAK SOSIAL, EKONOMI, DAN LINGKUNGAN UGM 2025.pdf`:
panel Daftar isi (bab + sub-bab bertitik, bisa diklik untuk scroll) → BAB II Dampak Sosial
(4 tema) → BAB III Dampak Ekonomi (5 tema) → BAB IV Dampak Lingkungan (5 tema).
Tiap sub-bab = satu tema Kepmen bernomor (2.1–4.5) dengan panel **Indikator penilaian resmi
Kepmen 361/M/KEP/2025** (indikator/definisi/kriteria/formula/satuan + klaster SDGs)
di samping analisis berita tema itu (metrik, 3 chart, tabel).

- API: payload `chapters` baru di `GET /analytics/story` (kunci lama tidak berubah;
  hanya scene `mode=impact` yang merendernya — scene `dampak-sdgs` sudah punya tampilan SDG sendiri).
  Urutan bab & nomor sub-bab: konstanta `CHAPTER_ORDER` di `api/app/services/story.py`;
  metadata indikator diambil dari `berita-dampak/scripts/kepmen_sdg.py`.
  Judul sub-bab di daftar isi memakai judul resmi laporan (field `report_title`, mis.
  4.2 "Konsumsi Energi yang Bertanggung Jawab", 3.4 "Kunjungan Akademik dan Pengeluaran
  Pengunjung Nasional") — bisa berbeda dari label pendek tema.
- Frontend: `web/src/laporan.tsx` (+ CSS `laporan-*` di `web/src/styles.css`),
  dipasang di `web/src/App.tsx` setelah Executive.
- Tabel **Daftar berita** tampil 5 berita per halaman dengan tombol
  ‹ Sebelumnya / Berikutnya (`page_size=5` dari API, diambil `NEWS_PAGE_SIZE`
  di `story.py`; renderer pager di `DataTable` pada `web/src/story.tsx`,
  CSS `.table-pager`). Tabel ringkas lain tetap tampil utuh; Unduh CSV tetap
  mengunduh seluruh baris.

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
- `deploy/legacy/README-streamlit-mysql.md` — arsip cara deploy lama (Streamlit + MySQL), lihat folder `legacy/`

## Arsip di luar repo

Sejak perapian 2026-09-21, file besar dan kredensial **tidak lagi disimpan di repo**:

| Dulu | Sekarang | Alasan |
|---|---|---|
| `ugm_analytics_dump.sql` (root, 23 MB) | `D:\ugm-analytics-arsip\database\ugm_analytics_dump_2026-08-29.sql` | Dump MySQL 29 Agu 2026 (18 tabel) — snapshot lama, bisa dibuat ulang dari DB live |
| `berita-dampak/data/analytics.sql` (155 MB) | `D:\ugm-analytics-arsip\database\analytics_2026-09-18.sql` | Dump MySQL 18 Sep 2026 (33 tabel) — duplikat isi DB live; bukan file yang dipakai `deploy/compose.yml` |
| `client_secret.json` (root) | `D:\ugm-analytics-arsip\secrets\client_secret.json` | Kredensial OAuth Google, belum dipakai fitur apa pun (login Google masih rencana) |
| `graphify-out/` | dihapus | Artefak tool analisis graf, bisa di-generate ulang |
| `push_log4.txt`, `tailscale_login.txt`, `.claude/` (kosong) | dihapus | Sampah sisa sesi |

`D:\ugm-analytics-arsip\README.md` menjelaskan isi + cara regenerasi. Folder itu DI LUAR git —
hapus saja kalau sudah tidak perlu.

Catatan: `deploy/compose.yml` mengharapkan `../migration-input/analytics.reader.sql`, dan folder
`migration-input/` tidak ada di mesin dev. Untuk deploy, ekspor ulang dari MySQL live dengan nama
itu — jangan mengandalkan dump di folder arsip.

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
