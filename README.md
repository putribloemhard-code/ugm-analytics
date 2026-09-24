# UGM Impact Analytics

Analisis dampak UGM berdasarkan Kepmendikti Saintek **361/M/KEP/2025**
(Indikator Dampak Sosial, Ekonomi, dan Lingkungan Perguruan Tinggi) dan
klaster **SDGs** — berbasis data publik yang bisa diambil offline.

Terakhir disinkronkan: **2026-09-23** — **dashboard Streamlit sudah dihapus**; aplikasi hanya
web React + API FastAPI, dijalankan lokal lewat `jalankan_web_baru.bat` (lihat "Streamlit
dihapus" di bawah).

## Subproyek

| Subproyek | Fokus | Status |
|---|---|---|
| `berita-dampak/` | Analisis berita dampak ugm.ac.id (14 tema Kepmen, 3 pilar, SDG, 44 unit kerja) | **Aktif** — pipeline + laporan statis + update mingguan (tampilan: `web/`) |
| `akreditasi/` | Kelengkapan data LED & LKPS (LAM-INFOKOM) | **Aktif** — registry 49 item + peta status 61 item + 3 pipeline data live + ekstraksi dokumen AI + generator Word (tampilan & login: `web/` halaman `/akreditasi`) |
| `matkul-sustainability/` | Mata kuliah terkait sustainability per fakultas/prodi | Selesai (2026-08-12) |
| `web/` + `api/` + `deploy/` | Frontend publik React/Vite + API FastAPI + paket deploy terisolasi | **Aktif — satu-satunya tampilan** — dashboard satu-halaman (Dampak / Dampak × SDGs / SDGs), ruang kerja Akreditasi (isi data, upload, ekstraksi AI, generate Word) + login, Profil Saya & Admin; `jalankan_web_baru.bat` untuk menjalankan lokal |
| `kkn-desa-binaan/` | Sebaran KKN & desa binaan (data dari eLOK — belum ada) | Kosong, butuh akses eLOK |
| `mahasiswa-afirmasi/` | Analisis kelompok afirmasi (data sensitif — belum ada) | Kosong, butuh akses resmi |

## Mulai cepat

**Aplikasi (web + API, lokal) — cukup klik dua kali:**

```bash
jalankan_web_baru.bat                 # API :8000 + web :3000 → buka http://127.0.0.1:3000
```

Butuh servis MySQL80 menyala (`.env` root berisi `MYSQL_*`). Halaman: `/dampak` (Analisis
Dampak), `/akreditasi` (ruang kerja LED/LKPS), `/profil`, `/admin`. Ekstraksi AI dokumen
akreditasi aktif bila `OPENAI_API_KEY` ada di `.env`.

Manual (dua terminal):

```bash
.venv\Scripts\python.exe web\dev_api_mysql.py      # API ke MySQL lokal, :8000
cd web && npm ci && npm run dev                    # web, :3000
# API produksi: cd api && uvicorn app.main:app --reload  (butuh PostgreSQL, env POSTGRES_*)
```

**Pipeline data berita-dampak (tanpa UI):**

```bash
cd D:\ugm-analytics\berita-dampak
..\venv\Scripts\python.exe scripts\update_mingguan.py         # update data dari ugm.ac.id
..\venv\Scripts\python.exe scripts\laporan_static.py          # regenerate laporan HTML
```

Laporan statis (tanpa server): `berita-dampak/laporan_berita_dampak.html`.

Catatan: ada DUA venv — `venv\` (pandas/plotly/requests/openai, untuk skrip pipeline di
subproyek) dan `.venv\` (fastapi/uvicorn/pytest + openai/pymupdf, untuk `api/` dan
`jalankan_web_baru.bat`). Jangan tertukar. Tes API: `cd api && ..\.venv\Scripts\python.exe -m pytest`.

Deploy terisolasi (Compose: postgres + mysql-reader + api + web + edge nginx,
subpath `/analytics/`) — lihat `deploy/README.md`; butuh Docker (belum terpasang
di mesin dev).

## Peta folder tingkat atas

| Folder | Isi |
|---|---|
| `berita-dampak/` · `akreditasi/` · `matkul-sustainability/` | Subproyek (lihat tabel di atas) |
| `web/` · `api/` | Aplikasi (React/Vite + FastAPI) — satu-satunya tampilan. `web/siapkan_logo.py` = rapikan logo mentah ke `web/public/logo/` |
| `deploy/` | Paket deploy terisolasi (Compose + Dockerfile + nginx). `deploy/legacy/` = file lama yang sudah tidak dipakai jalur aktif (compose MySQL-only, skrip migrasi DuckDB→MySQL, README deploy Streamlit) — disimpan untuk jejak, bukan untuk dijalankan |
| `docs/` | Dokumen tingkat workspace (PERENCANAAN, FRAMEWORK, ARCHITECTURE, PRD, listing ide) |
| `sumber/` | Referensi resmi (sharing, TIDAK boleh dihapus): `UGM Analytics.xlsx`, Kepmen 361 (PDF scan), Buku IKU (PDF), `picture/` (gambar mentah) |
| `venv/` · `.venv/` | Virtualenv Python (lihat catatan dua venv di atas) |
| `kkn-desa-binaan/` · `mahasiswa-afirmasi/` | Subproyek kosong (menunggu akses data) — hanya `.gitkeep` di `data/` + `scripts/` |

## Struktur & kepemilikan sumber (aturan 2026-09-21)

Aturan yang dipakai setelah perapian struktur:

1. **Sumber sharing** ada di dalam repo, di folder bersama: `sumber/` (dokumen & gambar mentah
   resmi), `web/public/` (aset web).
2. **Sumber per use case** ada di dalam folder use case masing-masing: `berita-dampak/`,
   `akreditasi/`, `matkul-sustainability/` — termasuk skrip, data, dan dokumen.
3. **Duplikasi aset yang disengaja** (jangan "dirapikan" tanpa alasan):
   - logo: `sumber/picture/` (mentah) → `web/public/logo/` (hasil `web/siapkan_logo.py`).
     Resolusinya beda, jadi bukan duplikat. Yang dipakai kode: `web/public/`.
4. **Ketergantungan runtime API → skrip subproyek** (sengaja, jangan dipindah):
   `api/app/domain/source.py` memuat modul dari `berita-dampak/scripts/` (`kepmen_sdg.py`,
   `unit_kerja.py`, `keywords.py`, `narasi_logic.py`, `sdg_keywords.py`) dan
   `akreditasi/scripts/` (`registry_kebutuhan_data.py`, `generate_template.py`,
   `ekstraksi_akreditasi.py`). Memindahkan file itu akan mematahkan `/analytics/story` dan
   ruang kerja akreditasi.
5. **Dump database & secret TIDAK disimpan di repo** — lihat "Arsip di luar repo" di bawah.

## Streamlit dihapus (2026-09-23)

Semua dashboard Streamlit (`berita-dampak/dashboard_berita_dampak.py` + `pages_app/`,
`akreditasi/dashboard_akreditasi.py`, `matkul-sustainability/dashboard_*.py`, `shared/style.py`)
dihapus setelah fiturnya dipindah ke web. Riwayatnya tetap ada di git.

Fitur akreditasi yang dulu hanya ada di Streamlit kini di `/akreditasi` (komponen
`web/src/akreditasi.tsx`, service `api/app/services/accreditation_workspace.py`):

| Fitur | Endpoint (`/api/v1/analytics/accreditation/...`) |
|---|---|
| Isi data per item LED/LKPS (tabel multi-baris & narasi), simpan = tulis ulang item | `GET workspace?prodi_id=&dokumen=`, `POST workspace/items/{item_id}` |
| Upload file (banyak sekaligus) + ekstraksi AI di latar, status per batch | `POST uploads`, `POST extractions` |
| Review hasil AI: isi sel kosong saja, tidak menimpa data manual, konflik antar file dikosongkan & dipilih user, dikonfirmasi saat Simpan | (bagian `draft` di `workspace`) |
| Tambah prodi baru | `POST programs` |
| Generate Word LED/LKPS + riwayat | `POST generate` |
| Unduh ulang laporan dari Profil | `GET history/{id}/file` |

Ikut diperbaiki: upload akreditasi di web selama ini selalu gagal 503 (`settings` tidak diimpor
di router), dan login API kini punya rate limit yang sama dengan Streamlit (5× gagal beruntun
dalam 15 menit → email dikunci sementara).

Juga dipindah (2026-09-23, lanjutan):
- **Update data berita** — halaman `/admin` → panel "Update data" (khusus admin akreditasi):
  `POST /api/v1/analytics/refresh` menjalankan `update_mingguan.py` di latar (interpreter
  `venv\` atau env `UGM_ANALYTICS_PYTHON`), `GET refresh-status` memberi status + tail log
  `berita-dampak/logs_update_dashboard.txt`. Lock `data/.update_lock` dicek (PID yang sudah mati
  dianggap lock yatim). Setelah selesai, cache `/story` dibuang sekali.
- **Narasi LLM** — `berita_narasi_cache` kini dibaca `/story`: ringkasan eksekutif
  (`exec_berdampak` / `exec_berdampak_sdgs`) dan insight pilar (`pilar_<pilar>`, hanya mode
  Dampak × SDGs), **hanya saat filter default** (aturan sama dengan Streamlit). Field
  `narrative_source: "llm" | "template"`; UI memberi label "dirangkai AI".
- **Deploy** — lihat `deploy/README.md`: skrip migrasi kini membuat skema benar (PK, UNIQUE,
  IDENTITY, boolean) dan punya mode `--perbaiki-skema` untuk server yang sudah dimigrasi dengan
  skrip lama (**WAJIB dijalankan sebelum versi ini dipakai di server lama** — tanpanya login pun
  gagal karena `akreditasi_login_attempts.berhasil` masih BIGINT). Ekstraksi AI diaktifkan lewat
  `deploy/openai.env` (opsional). Image API kini ikut memuat `generate_template.py` dan
  `ekstraksi_akreditasi.py` (dulu tertinggal → generate Word/ekstraksi pasti gagal di container).

Verifikasi 2026-09-23: 89 tes API; alur tulis di MySQL asli (dalam transaksi yang di-rollback —
jumlah baris sebelum/sesudah identik) termasuk ekstraksi dengan OpenAI sungguhan (PDF 3 halaman,
7 batch, 44 kolom ditemukan, data manual tidak ditimpa); migrasi lama vs baru diuji di
PostgreSQL 16 portabel (registrasi/login/upload/simpan gagal sebelum `--perbaiki-skema`, lolos
sesudahnya dan pada migrasi baru).

## Bagian "Sumber" di halaman Dampak (2026-09-24)

Urutan `/dampak`: pembuka (judul + pencarian, **tanpa angka**) → **Bagian I Sumber Data**
(`#sumber`) → Bagian II Tiga jalur → Bagian III Analisis (Dampak, Dampak × SDGs, SDGs).
Bagian lama "Data & metodologi" dihapus; isinya (catatan lower-bound & beda metode) pindah ke
Sumber, dan anchor lama `#metodologi` diarahkan ke `#sumber`.

- Diagram silsilah data (`web/src/sumber.tsx`, CSS `.lineage`): tiap sumber = satu jalur
  sumber → diambil → memuat konten dampak (+ persentase) → per dampak (Sosial/Ekonomi/Lingkungan).
  Jalur 01 berita ugm.ac.id (sitemap & RSS, rentang tahun, ID/EN); jalur 02 mata kuliah dari web
  publik tiap prodi (catatan: >20 situs, dikurasi ke satu berkas). Sumber internal (sistem
  kurikulum UGM) ditampilkan putus-putus dengan status "Belum ada akses".
- Tabel "Berita yang memuat konten dampak": cari judul, saring per dampak, 10 per halaman;
  judul membuka artikel asli di tab baru (hanya URL http/https yang dijadikan tautan).
  Di HP tiap baris menjadi kartu.
- API: `GET /api/v1/analytics/sources` dan `GET /api/v1/analytics/sources/news?page=&page_size=&q=&pilar=`
  (`api/app/services/sources.py`). Dihitung dari frame yang sudah di-cache `StoryService`
  (ringkasan ±0,3 detik, tabel ±50–200 ms); query SQL langsung sempat 3–15 detik.

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

## Sumber data kedua: mata kuliah sustainability (2026-09-23)

Dashboard dampak tidak lagi hanya berita. Data kurikulum mata kuliah ikut tampil
dan dikaitkan ke tema Kepmen:

- Sumber: `matkul-sustainability/data/Deskripsi Matkul Kepmen.csv` (kurasi manual,
  8.465 baris penawaran MK) + `Ringkasan Indikator Kepmen.md`/`.json` (konversi dari
  PDF; angka resmi & catatan metode — PDF asli tetap disimpan). CSV dipisah `;`,
  encoding **cp1252** — bukan UTF-8.
- Angka resmi (selaras Ringkasan): 511 baris **Substansial – dihitung** = **453 MK unik**
  setelah dedup nama; 142 baris *Parsial/bergantung topik* **tidak** dihitung
  (Kepmen no. 2: MK yang menyinggung sepintas tidak dihitung). Tabel status Ringkasan
  mencatat total 8.463 (bukan 8.465) karena 2 baris berstatus kosong.
- **Angka resmi hidup di kode**: `api/app/services/ringkasan_kepmen.py` (STATUS_RESMI,
  KRITERIA_RESMI, CATATAN_METODE_RESMI — butir 1-7 Ringkasan). `load_matkul()` selalu
  cek-silang CSV vs angka resmi (`cek_silang_csv`) dan log warning bila berbeda;
  test `test_load_matkul_csv_sesuai_ringkasan_resmi` mengunci angkanya.
- Payload `mata_kuliah` bawa `kriteria_resmi` (jumlah MK resmi per kriteria a-j:
  a=165, b=116, c=42, d=59, e=33, f=142, g=127, h=35, i=117, j=130) dan
  `catatan_metode` — keduanya tampil di panel web (detail Angka resmi + Catatan metode).
- **Tagging ke 14 tema Kepmen (2026-09-24)** — `tag_tema()` di `api/app/services/matkul.py`,
  satu baris per (MK unik, tema) dengan kolom `dasar` supaya tiga jenis kaitan tidak tercampur:

  | Dasar | Tema | Cara |
  |---|---|---|
  | Indikator resmi | 4.5 Pendidikan & Penelitian | semua MK Substansial (453) — **satu-satunya angka indikator resmi** |
  | Kriteria a–j (kurasi manual) | 4.1 Energi (c), 4.2 Konsumsi Bertanggung Jawab (d, e), 4.4 Keanekaragaman Hayati (f, g, h, i) | dari kolom `kriteria_kepmen_match` MK Substansial |
  | Keyword kurikulum | 2.1 Pendidikan Inklusif, 2.2 Penelitian & Inovasi, 2.3 Pengabdian, 2.4 Kebijakan Publik, 3.2 Kolaborasi Riset, 3.3 Kewirausahaan, 4.3 Transportasi | `LEKSIKON_TEMA` (dari definisi indikator resmi, BUKAN keyword berita — "seminar"/"mata kuliah" menyeret hampir semua MK), awal-kata; diperiksa manual per MK |
  | Tidak ada padanan | 3.1 Pengajaran & Pembelajaran, 3.4 Kunjungan Akademik, 3.5 Pengeluaran Institusi | indikator berupa pengeluaran (Rp) → 0 MK + alasan |

  Pengecualian yang disengaja: Transportasi hanya dicocokkan ke **nama** MK ("transport
  polutan", "Praktikum Ticketing" tidak masuk); "berkebutuhan khusus" di kedokteran gigi bukan
  Pendidikan Inklusif. Hasil data asli: 659 MK unik terkait (Lingkungan 472 · Sosial 123 ·
  Ekonomi 69) dari 26 fakultas/sekolah.
- **Mode SDGs** — `tag_sdg()`: MK dicocokkan langsung ke 17 SDG dengan kamus yang SAMA dengan
  berita (`sdg_keywords.py`, konvensi ≤5 huruf = kata utuh). Kamusnya luas (SDG 9 947 MK karena
  "teknologi/penelitian") → ditandai indikatif di UI. Mode Dampak × SDGs memakai klaster SDG
  tema-tema MK (mapping Kepmen), bukan keyword SDG.
- API: kunci `mata_kuliah` di `GET /analytics/story` (`tersedia:false` bila CSV tak ada);
  field baru `mode` (`tema`/`sdg`) dan `per_tema` (rekap 14 tema termasuk yang 0). Blok mengikuti
  filter GLOBAL dampak/tema/SDG — bukan pilar yang dibuka di drill-down. Tiap sub-bab laporan
  (2.1–4.5) membawa `mata_kuliah` {jumlah, dasar, catatan, fakultas, tabel}. Baris tabel hanya
  membawa kolom yang ditampilkan (tanpa deskripsi) dan API kini memakai `GZipMiddleware`
  (respons /story mode Dampak ±1,3 MB → ±260 KB).
- Frontend (`web/src/laporan.tsx`): `MataKuliahPanel` tampil di ketiga bagian (akhir laporan
  Dampak, Dampak × SDGs, SDGs); `KurikulumTemaPanel` = kotak "Mata kuliah terkait tema ini" di
  setiap sub-bab, tetap tampil walau tema itu tanpa berita.
- Verifikasi 2026-09-24: 92 tes API; UI headless dengan data MySQL asli (hanya baca) — 3 panel +
  14 kotak sub-bab, desktop 1440px & HP 390px tanpa overflow/error.

## Dokumentasi

- `docs/PERENCANAAN.md` — tujuan, prinsip, backlog ide, milestone, status per subproyek
- `docs/FRAMEWORK.md` — stack, peta repo, pipeline, konvensi, aturan MySQL/DuckDB
- `docs/ARCHITECTURE-UGM-ANALYTICS-DAMPAK-vNEXT.md` — arsitektur lengkap per layer + temuan operasional
- `docs/PRD_FRONTEND_NON_STREAMLIT.md` — PRD migrasi Streamlit → React/Vite + FastAPI
- `docs/REVIEW_WEB_BARU_2026-09-21.md` — review dashboard web baru (temuan + perbaikan yang sudah dikerjakan)
- `docs/listing-ide-analisis-dampak.md` — ide backlog
- `berita-dampak/README.md` + `PIPELINE.md` + `docs/OUTPUT.md` — subproyek berita-dampak
- `akreditasi/README.md` + `PIPELINE.md` — subproyek akreditasi
- `matkul-sustainability/README.md` + `PIPELINE.md` — subproyek matkul
- `docs/` berisi dokumen historis yang masih menyebut Streamlit — status terkini ada di README ini
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

- Python venv: `venv/` (pandas, plotly, requests, bs4, duckdb,
  openpyxl, pymupdf, rapidocr-onnxruntime, sqlalchemy, pymysql, python-dotenv,
  openai). Bukan matplotlib/kaleido — output statis pakai plotly `write_html`.
- Penyimpanan: **MySQL** `ugm_analytics` (berita-dampak + akreditasi; kredensial
  `.env` root, contoh di `.env.example`). `matkul-sustainability` masih CSV/DuckDB
  lokal. API publik membaca **PostgreSQL** (env `POSTGRES_*`).
- `mysql` CLI tidak ada di PATH mesin dev — query manual pakai Python + SQLAlchemy
  (contoh di `berita-dampak/docs/OUTPUT.md`).
- Node: `node v24` + `npm 11` terpasang (untuk `web/`). Docker belum terpasang.
- OS: Windows; terminal pakai git-bash (MSYS).
