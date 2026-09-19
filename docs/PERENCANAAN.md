# PERENCANAAN — UGM Impact Analytics

Terakhir disinkronkan: **2026-09-19** (dari kondisi repo + MySQL live, bukan salinan dokumen lama).

## Tujuan

Mengidentifikasi, mengukur, dan memvisualisasikan **dampak UGM** terhadap
Sosial, Ekonomi, dan Lingkungan sesuai **Kepmendikti Saintek 361/M/KEP/2025**
(Indikator Dampak Sosial, Ekonomi, dan Lingkungan Perguruan Tinggi), serta
memetakannya ke klaster **SDGs**. Data diambil dari sumber publik (ugm.ac.id)
atau data internal kampus — TANPA akses eLOK yang disetujui.

Sejak 2026-09-06 ruang lingkup bertambah satu jalur non-analitik:
**akreditasi/** (kelengkapan data LED/LKPS LAM-INFOKOM) — registry + peta status
sumber + pipeline data live + ekstraksi dokumen + generator Word, berbagi
database MySQL yang sama. Sejak 2026-09-19 bertambah jalur aplikasi publik:
**web/ + api/ + deploy/** (React/Vite + FastAPI + Compose), belum dijalankan
di mesin dev.

## Prinsip

- **Offline-first**: kerjakan dengan data lokal yang sudah ada; minta izin
  dulu sebelum scraping/network ke eLOK. ugm.ac.id (RSS + sitemap) sudah
  disetujui.
- **Satu sumber kebenaran**: mapping topik → Topik Resmi Kepmen → SDG diambil
  dari `sumber/UGM Analytics.xlsx` (sheet "Konten UGM Berdampak" + "#Ref") dan
  PDF Kepmen asli — jangan menebak. Daftar 44 fakultas/sekolah/unit kerja UGM
  berasal dari pemilik project (`berita-dampak/scripts/unit_kerja.py`).
- **Lower-bound & eksplorasi jelas**: angka hasil keyword-match adalah
  batas bawah (bukan angka resmi); label "eksplorasi — cek manual" dipakai
  di dashboard sampai divalidasi.
- **Fail-safe by default**: kolom/fitur baru wajib punya jalur fallback aman
  kalau prasyaratnya belum ada (`db.column_exists()` sebelum scan kolom `isi`,
  `fetch_gagal_count` berhenti otomatis setelah 3x gagal, narasi LLM skip
  aman ke template pandas kalau API key kosong/gagal).
- **Angka di dokumen = snapshot**: verifikasi runtime selalu dari MySQL/API
  live, jangan hardcode angka dokumen ke dalam kode.
- **Terse & terdokumentasi**: tiap subproyek punya README + PIPELINE +
  DASHBOARD; semua file terkonsolidasi di folder proyek.

## Backlog ide (dari docs/listing-ide-analisis-dampak.md)

1. ~~Matkul Sustainability~~ — **SELESAI (2026-08-12)**: keyword 9 topik Kepmen
   pada deskripsi matkul → bar per fakultas, drill-down per prodi, tren.
   `matkul-sustainability/` (CSV/DuckDB lokal; 382 matkul bersih, 23 terkait
   sustainability = 6,0%; Kehutanan 10/17 = 58,8%).
2. ~~Berita Dampak~~ — **SELESAI (2026-08-18) + diperluas terus s/d 2026-09-01**:
   berita ugm.ac.id → 14 tema Kepmen → 3 pilar → SDG. `berita-dampak/`.
   Termasuk update otomatis mingguan, isi lengkap artikel, tagging unit kerja,
   dan mode "SDGs saja".
3. ~~Akreditasi LED/LKPS~~ — **TIDAK ADA DI BACKLOG AWAL, DIKERJAKAN 2026-09-06 → berjalan**:
   `akreditasi/`. Tiga fase: (1) registry 49 item + `data_source_map.json` 61 item
   (5 tersedia / 41 kurang akses data / 15 perlu penyusunan manusia); (2) pipeline data
   live — `pipeline_item_tersedia.py`, `pipeline_sinta.py` (publikasi Scopus/SINTA),
   `pipeline_dcse_berita.py` (arsip RSS evidence); (3) ekstraksi dokumen upload dua
   tier (pattern-matching tanpa AI → fallback LLM) + `generate_laporan_live.py`.
   Cakupan data: 20 fakultas / 18 prodi (FMIPA), `akreditasi_data_manual` 118 baris
   terisi (14 item), 237 baris preview ekstraksi, login dibatasi domain UGM.
4. KKN Desa Binaan — **BELUM**: folder `kkn-desa-binaan/` masih kosong; butuh
   data eLOK (kkn.ugm.ac.id / pengabdian.ugm.ac.id/wilayah-binaan/). Perlu izin.
5. Mahasiswa Afirmasi — **BELUM**: folder `mahasiswa-afirmasi/` masih kosong;
   data sensitif (tracer study/SIMASTER), perlu akses resmi.
6. Frontend non-Streamlit + API — **DIBANGUN (2026-09-19)**: `web/` (React+Vite)
   + `api/` (FastAPI) + `deploy/` (Compose terisolasi). Belum dijalankan di
   mesin lokal; deploy ke host BTD = milestone terpisah. Lihat
   `docs/PRD_FRONTEND_NON_STREAMLIT.md`.

## Milestone

| Tanggal | Capaian |
|---|---|
| 2026-08-12 | matkul-sustainability selesai (scrape eLOK → tagging Kepmen → dashboard + laporan) |
| 2026-08-18 | berita-dampak pipeline awal: sitemap + RSS + fetch detail + tagging 4 topik inti + dashboard + laporan HTML |
| 2026-08-19 | Tagging Kepmen/SDG resmi; bagian "Peta Kepmen & SDGs"; filter pilar; akses dashboard dari laptop lain (firewall 8766 + Tailscale) |
| 2026-08-20 | 14 tema lengkap + SDG dari sheet #Ref; perluasan keyword berbasis validasi sampel (1.181 → 1.969 berita unik); update otomatis (`update_mingguan.py` + lock + tombol + cron Sabtu 06:00); dokumentasi lengkap + Git repo |
| 2026-08-21 | Re-tag keyword bersumber detailing tabel Kepmen (OCR); mode "SDGs saja" (mapping langsung seluruh sitemap); fix heatmap plotly imshow |
| 2026-08-24 | Konvensi penjelasan chart (`💡 penjelasan` + tooltip) di dashboard & laporan; IP LAN dinamis di `buka_akses_dashboard_admin.bat` |
| 2026-08-28 | Handover deployment report (`docs/HANDOVER_DEPLOYMENT_REPORT_UGM_ANALYTICS_20260828.pdf`) |
| 2026-08-29 | **Migrasi penuh DuckDB → MySQL** (9 script pipeline baca/tulis langsung MySQL; upsert batch + retry + PK url; `sync_mysql.py` dihapus) |
| 2026-09-01 | **Isi lengkap artikel** (`fetch_backlog.py`, selector `div.inner-content` + fallback `<div>` template lama; `kredit` dipisah; `fetch_gagal_count` cap 3x) → 32.190/32.191 isi terisi (99,99%); `normalisasi.py` auto-passthrough kolom baru; **tagging 44 fakultas/sekolah/unit kerja** (`tag_unit_kerja.py` + guard leakage lintas-universitas) |
| 2026-09-06 | Subproyek **akreditasi** (registry 49 item LED/LKPS + dashboard + generator Word); berita-dampak dipecah **multipage** (`pages_app/`); selector scope Universitas/Prodi; CSS bersama lintas dashboard |
| 2026-09-08 | Perbaikan filter Lampiran Dampak & SDG (vertikal, dampak kosong = hasil kosong) |
| 2026-09-11 | Akreditasi **Fase 1**: `data_source_map.json` — peta status sumber 61 item (5 tersedia / 41 kurang akses data / 15 perlu penyusunan manusia); PDF LED/LKPS lama hanya dipakai untuk struktur, bukan isi |
| 2026-09-16 | Akreditasi **Fase 2 & 3**: 3 pipeline data live (item tersedia, SINTA, arsip RSS dcse) + ekstraksi dokumen dua tier (pattern-matching tanpa AI → fallback LLM) + `generate_laporan_live.py`; data manual lama diarsipkan ke `akreditasi_data_manual_arsip_pdf` (2.292 baris) |
| 2026-09-18 | **Login akreditasi (Fase A+B)** — dibatasi domain UGM (ugm.ac.id / mail.ugm.ac.id) + admin akun pertama + blokir/hapus akun; multipage berita-dampak di-overhaul (visual, pencarian, laporan Word); narasi LLM **Gemini → OpenAI** |
| 2026-09-19 | Merge branch `dev.yayan`: **frontend React/Vite (`web/`) + API FastAPI (`api/`) + paket deploy terisolasi (`deploy/`)**; hapus `ugm_news.duckdb`; hapus script yatim; perketat `.gitignore` (dump/secret) |

## Status per subproyek (2026-09-19)

| Subproyek | Status | Penyimpanan |
|---|---|---|
| `berita-dampak/` | Aktif — pipeline + multipage dashboard + laporan + update mingguan | MySQL `ugm_analytics`, prefix `berita_` |
| `akreditasi/` | Aktif — registry + peta status sumber + 3 pipeline live + ekstraksi dokumen (pattern & AI) + dashboard + generator Word + login domain UGM | MySQL `ugm_analytics`, prefix `akreditasi_` |
| `matkul-sustainability/` | Selesai (2026-08-12), tidak berubah | CSV + DuckDB lokal |
| `kkn-desa-binaan/` | Kosong — butuh data/izin eLOK | — |
| `mahasiswa-afirmasi/` | Kosong — butuh akses resmi | — |
| `web/` + `api/` + `deploy/` | Dibangun, belum dijalankan lokal; deploy menunggu keputusan infra | API baca PostgreSQL |

## Roadmap (ide berikutnya)

- **Deploy stack baru** (`deploy/compose.yml`) ke host BTD: Postgres + api +
  web + edge nginx subpath `/analytics/`; impor dump lewat `mysql-reader` +
  `deploy/migrate_mysql_to_postgres.py`. Butuh keputusan infra + persetujuan
  eksplisit (lihat `deploy/README.md`, gate pra-deploy).
- **Verifikasi parity** React vs Streamlit untuk setiap mode/filter sebelum
  Streamlit dipensiunkan (Streamlit tetap baseline rollback).
- Validasi manual sampel berita per tema untuk menaikkan status dari
  "eksplorasi" ke "terverifikasi" (turunkan false positive).
- Ekspor ringkasan per pilar/tema/SDG ke Excel (template Kepmen siap isi).
- Akreditasi: perluas dari 18 prodi FMIPA ke fakultas lain; RBAC per prodi +
  audit log + cookie `Secure` (masih `False` untuk dev/HTTP) sebelum dianggap
  siap produksi (lihat "Deferred: accreditation phase" di PRD).
- KKN Desa Binaan & Mahasiswa Afirmasi — menunggu data/izin.
