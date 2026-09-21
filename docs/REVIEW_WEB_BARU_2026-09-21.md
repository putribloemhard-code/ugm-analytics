# Review dashboard web baru (React + API) — branch `putri.update`

Tanggal review: 2026-09-21 · Reviewer: agen Hermes · Metode: baca kode, kueri MySQL live,
panggil API sungguhan, dan jalankan UI di browser headless (Edge) — bukan sekadar baca ringkasan.

Prasyarat yang dipakai: MySQL lokal jalan (port 3306), API `web/dev_api_mysql.py` (port 8000),
Vite dev server (port 3000). Kedua proses sudah jalan sebelum review; review ini TIDAK mematikan
keduanya.

---

## 1. Kesimpulan singkat

Klaim di ringkasan Anda **sebagian besar terbukti benar dan terverifikasi**. Yang saya temukan:
3 bug nyata (1 di antaranya cukup terlihat pengguna), 2 klaim yang kurang tepat, dan beberapa
catatan kualitas/risiko. Rincian di bawah.

Skor kasar: tampilan & struktur data **bagus**; kebersihan integrasi (SQL portabel, isolasi test)
**perlu sedikit kerja** sebelum PR ke Yayan.

### 1.1 Status perbaikan (dikerjakan 2026-09-21, branch `putri.update`)

| # | Temuan | Status |
|---|---|---|
| §4.1 | `/analytics/news` filter SDG → 503 di MySQL | **Sudah diperbaiki** — helper `pipe_list_contains()` di `services/sqlcompat.py`; terverifikasi 200 |
| §4.2 | `test_postgres_config` gagal saat suite dijalankan | **Sudah diperbaiki** — `settings` dibaca saat dipanggil (proxy + `load_settings()`); `pytest tests` = 34 passed |
| §4.3 | cache `StoryService` berkunci `id(engine)` | **Sudah diperbaiki** — kunci objek engine + `clear_cache()` + batas entri |
| §5.1 | label rail menutupi panel filter/insight | **Sudah diperbaiki** — label disembunyikan < 1500px (tampil saat hover/fokus) |
| §5.2/§5.5 | basis angka metrik saat filter unit aktif | **Belum** (butuh keputusan Anda soal basis mana yang benar) |
| §4.4 | label halaman berita (1.486 vs 1.966) | **Belum** — perlu keputusan basis hitungan |
| §5.3 | format angka campur (titik vs koma) | **Belum** — sengaja mengikuti dashboard lama |
| §5.4 | kalimat "pertumbuhan -22.2%" | **Belum** — ada di `narasi_logic.py` (dipakai dua dashboard) |
| §5.6–5.8 | heatmap sempit, timestamp mentah, judul kartu SDGs | **Belum** |

Tambahan di luar review (permintaan Anda): tombol "Masuk" di header dihapus, dan fitur
**Profil Saya** + **Admin** dari dashboard Streamlit lama diintegrasikan ke web baru —
lihat §9.

---

## 2. Verifikasi angka (MySQL live vs UI vs API)

Semua di bawah diambil dari MySQL `ugm_analytics` dan dari API yang sedang jalan.

| Angka | Nilai terverifikasi | Sumber |
|---|---|---|
| berita (baris tabel) | 32.228 | `berita_berita` |
| sitemap | 32.281 | `berita_sitemap` |
| URL bertanda SDG | 31.873 | `berita_sitemap_sdg` |
| berita dampak unik | **19.829** | `berita_berita_kepmen_all` |
| Sosial / Ekonomi / Lingkungan | **12.534 / 8.701 / 7.430** | idem (unik per dampak) |
| cakupan | 61,4% | 19.829 / 32.281 (hero memakai pembagi sitemap) |

Angka 19.829 dan 12.534 di ringkasan Anda **cocok persis**. Tema terbanyak dampak Sosial
("Pengabdian Masyarakat" 7.405) juga cocok dengan metrik kartu.

### Jumlah chart — cocok, dengan satu catatan cara hitung
- Mode **Dampak**: 8 chart detail + 9 chart lintas = **17** ✔
- Mode **Dampak × SDGs**: 10 + 13 = **23** ✔
- Mode **SDGs**: **4** ✔
- Total yang dirender di halaman: **30** chart sekaligus (mode Dampak aktif 11 terlihat + 19 dari
  dua mode lain yang sudah ikut termuat saat digulir) — konsisten dengan hitungan API.
- Catatan: angka 17/23 hanya benar untuk **satu dampak terpilih**. Ketiga kartu dampak
  (Lingkungan/Ekonomi/Sosial) masing-masing punya 17/23 chart sendiri, jadi kalau ada yang
  menghitung "semua chart yang tersedia di mode Dampak" jawabannya 51. Ringkasan sebaiknya
  menyebut "per dampak terpilih" supaya tidak ambigu.

---

## 3. Yang terbukti jalan (saya uji sendiri, bukan dari deskripsi)

- **Ringkasan hero**: 32.228 / 19.829 / 61,4% ter-render, hitung-naik berjalan, kolom pencarian ada.
- **Pencarian**: "energi" → `/dampak?pillars=Lingkungan&topics=energi` + kalimat penjelasan
  "Hasil pencarian \"energi\" menampilkan dampak Lingkungan, tema Energi." ✔
- **Filter**: dropdown centang jalan; memilih "Fakultas Farmasi" memicu **tepat satu** request
  `/analytics/story?...&units=fakultas_farmasi&pillar=Lingkungan` dan **tidak** me-refresh bagian
  lain (bagus, tidak boros). Ringkasan pilihan ("Fakultas Farmasi", "1 filter aktif") benar.
- **Pemilih tema kata kunci**: ganti tema → judul chart berubah jadi
  "Keyword pemicu match — Keanekaragaman Hayati" + "15 kata teratas — …" ✔
- **Tab per dampak**: 5 tab (Ringkasan & Insight, Tema Resmi Kepmen, SDGs Terkait*, Tren &
  Musiman, Kata Kunci & Berita, Fakultas/Unit Kerja) semuanya berisi chart, tidak ada tab kosong.
  (*SDGs Terkait hanya muncul di mode Dampak × SDGs — sesuai desain.)
- **Klik kartu dampak**: pindah ke Ekonomi → heading "Detail dampak: Ekonomi", angka ikut berubah
  (7.430 → 8.701), data lama diredupkan selama memuat (tidak ada lompatan halaman) ✔
- **Mode gelap**: tema berpindah, tersimpan di localStorage, label tombol berubah "Mode terang",
  latar `rgb(11,31,46)`. Kontras teks utama bagus.
- **Mobile 390px**: tidak ada overflow horizontal (`scrollWidth == clientWidth == 390`),
  rail disembunyikan, kartu metrik & panel filter menumpuk rapi, chart bar tetap utuh.
- **Peta scroll (rail)**: tepat muncul mulai **1340px** dan hilang di 1339px — sesuai klaim.
  Label melayang hanya tampil saat item aktif/hover (bukan selalu).
- **Daftar berita**: 5 baris per halaman, "Halaman 1 dari 1.486" (19.829/5 ≈ 1.966; angka 1.486
  berasal dari jumlah baris tabel yang lebih kecil dari jumlah URL unik — lihat §4.4).
- **Laporan Word**: POST `/analytics/reports` → 200, 41 KB, terdeteksi "Microsoft Word 2007+" ✔
- **Akreditasi**: `/analytics/accreditation` → 200 (94 KB) — **503 yang dulu memang sudah hilang** ✔
- **Gerbang login**: halaman akreditasi menampilkan gerbang "Masuk / Daftar akun baru";
  login salah → "Email atau password salah." (401), tetap di gerbang.
- **Validasi domain**: registrasi `uji@example.com` ditolak "Gunakan email @ugm.ac.id atau
  @mail.ugm.ac.id." — dan **tidak menulis apa pun ke DB**. DB tetap: 2 user (id 1 & 5, keduanya
  akun Anda, dibuat 2026-09-17), 0 sesi, 1 upload, 8 percobaan login. Klaim "tidak menulis akun
  uji ke MySQL asli" **benar**.
- **Build produksi**: `npm run build` lolos (tsc + vite), bundle 309 KB (97 KB gzip), CSS 34 KB.
  Tidak ada error TypeScript.
- **Endpoint story**: 1,2–3,3 detik per permintaan dengan cache 5 menit; tidak ada error 5xx.

---

## 4. Temuan yang perlu diperbaiki

### 4.1 BUG (terlihat pengguna) — tautan berbagi dengan filter SDG membuat daftar berita gagal

Repro: buka `http://127.0.0.1:3000/dampak?year_from=2004&year_to=2026&sdgs=13`

- API: `GET /analytics/news?...&sdgs=13` → **HTTP 503**
- UI: kotak merah "Daftar berita belum dapat dimuat." (chart & tabel lain tetap tampil, 26 chart)

Penyebab: `api/app/services/news.py:73` memakai
`:sdg = ANY(string_to_array(replace(COALESCE(bk.sdg,''),'|',','), ','))`
— `string_to_array` **hanya ada di Postgres**, tidak ada di MySQL. Jalur ini hanya terpicu bila
`mode=impact` **dan** filter `sdgs` diisi; mode `sdgs` memakai jalur lain sehingga aman (saya uji:
`mode=sdgs&sdgs=13` → 200).

Ini penting justru karena **fitur pencarian menghasilkan URL seperti itu**: mengetik "SDG 7" akan
mengarahkan ke `/sdgs?sdgs=7` (aman), tetapi siapa pun yang menambahkan `sdgs=` ke URL `/dampak`
langsung kena. Perbaikan: buat helper dialek di `services/sqlcompat.py` (mis.
`sdg_list_match(engine, column)` → versi Postgres `string_to_array`, versi MySQL
`FIND_IN_SET(:x, REPLACE(COALESCE(col,''),'|',','))`), lalu pakai di `news.py`. Ini juga menutup
sisa "SQL khusus Postgres" yang belum dipindah — sejalan dengan tujuan portabilitas di ringkasan.

### 4.2 BUG (kualitas peringkat) — `test_postgres_config` gagal saat dijalankan bersama test lain

```
pytest tests -q                       -> 1 failed, 19 passed
pytest tests/test_postgres_config.py  -> 1 passed
pytest tests/test_api_contracts.py tests/test_postgres_config.py -> 1 failed
```

Penyebab: `app/config.py` membuat `settings = Settings()` saat **impor** (baris 38), jadi nilai env
tertangkap sekali saja. `monkeypatch.setenv` di test tidak berpengaruh karena `app.config` sudah
terimpor oleh test lain. Terbukti: setelah `importlib.reload(app.config)` + `reload(app.db)`,
URL-nya benar (`postgresql+psycopg postgres 5432 ugm_analytics ugm_app`).

Perbaikan minimal: di dalam test, impor `app.config` lalu `importlib.reload(...)` sebelum
`from app.db import build_database_url`. Ringkasan Anda menyebut "19 test lolos" — kalau
dijalankan dengan `python -m pytest tests`, hasil sebenarnya **1 gagal, 19 lolos**.

### 4.3 BUG (mudah, tapi mengunci fitur) — cache `StoryService` tidak pernah dibuang saat engine berganti

`StoryService._cache` adalah **class attribute** ber-kunci `id(self.engine)`
(`api/app/services/story.py:1095,1123`). `id()` bisa didaur ulang Python setelah objek engine lama
di-GC — bila itu terjadi, permintaan bisa menyajikan data dari engine lama (mis. MySQL vs Postgres
saat pindah mode pratinjau/produksi). Selain itu `id()` antar-instance engine berbeda memang
menghasilkan entri baru, jadi cache membengkak pelan-pelan.

Perbaikan: simpan `(engine, timestamp, frames)` dan bandingkan dengan `is`, atau pindahkan cache ke
`self` per-instance + sediakan `StoryService.clear_cache()`. Ini juga memudahkan test integrasi.

### 4.4 Klaim yang kurang tepat — "19 test lolos" dan "1.486 halaman berita"

- Test: lihat §4.2 (1 gagal bila dijalankan sebagai suite).
- Halaman berita: label UI "Halaman 1 dari 1.486" tidak sama dengan `total/5` (19.829/5 ≈ 1.966)
  karena endpoint memakai `COUNT(DISTINCT b.url)` sementara baris tabel berisi satu baris per
  pasangan berita×tema. Bukan bug fatal, tapi pengguna bisa bingung ("kok 1.486 halaman padahal
  19.829 berita"). Pertimbangkan menyamakan basis hitungan atau memberi keterangan singkat.

### 4.5 SQL portabilitas — hampir bersih, satu titik tertinggal

Sisanya sudah bersih: `NULLS LAST`/`RETURNING`/`split_part` sudah diganti (`sqlcompat.py`,
`accreditation_auth.py:86`, `accreditation_upload.py:50`), dan tidak ada lagi `::`, `ILIKE`,
`date_trunc`, `jsonb`, `ON CONFLICT`, `DISTINCT ON` di `api/app/`. Tinggal `string_to_array`
(§4.1). Catatan tambahan: `LIMIT`/`OFFSET` dipakai di `news.py` dan `accreditation.py` — valid di
keduanya, aman.

---

## 5. Catatan kualitas tampilan

**Bagus**
- Hero, tipografi editorial, dan palet navy/kuning sangat dekat dengan acuan laporan dekan FMIPA
  (struktur `cold-open`, `chapter-intro`, `story-scene`, `insight`, rail 01–05 semuanya selaras).
- Kontras teks kecil saya ukur: `.chart-note` 7,16:1, `.filter-count` 9,28:1, `.section-kicker`
  10,66:1 — di atas ambang WCAG AA.
- Tidak ada error JavaScript di konsol; satu-satunya "error" adalah 401 `/accreditation/auth/me`
  yang memang normal untuk pengunjung belum login.
- Aksesibilitas di atas rata-rata: `skip-link`, `role="tablist"`, `aria-pressed`, `aria-live`,
  `caption.sr-only`, dan `role="img"` + `aria-label` pada chart.

**Perlu diperhatikan**
1. **Label rail menutupi konten (paling terlihat).** Label melayang rail aktif berakhir di x=1371
   pada layar 1440px, sedangkan panel filter dan kotak insight membentang sampai x=1320 — jadi label
   "Analisis 1 / 3 · Dampak" menimpa sisi kanan panel filter/insight, dan di bawah 1400px
   menutupi area slider tahun. Di acuan FMIPA label ini juga ada, tapi di sini bertabrakan karena
   lebar kolom konten (1200px) + rail yang menempel. Saran: pada `@media (max-width: 1500px)`
   sembunyikan label (biarkan tooltip saat hover), atau kurangi lebar konten jadi ~1100px.
2. **Metrik kartu bisa salah baca saat filter unit aktif (temuan paling penting setelah §4.1).**
   Akarnya ada di `api/app/services/story.py:346-391`: `b` difilter unit kerja (baris 349-350) dan
   `t` dibangun dari `b` (baris 356), tetapi `generate_executive_summary` dipanggil dengan
   `b` dan `t` **bukan** yang terfilter (`b` asli & `t_nounit`) — sengaja, mengikuti
   `page_dampak.py`. Akibatnya, dengan filter "Fakultas Farmasi" (terverifikasi lewat API):
   - kartu "Total berita dampak" = **383** (basis terfilter unit), kartu "Sorotan 2026" = 16
     (basis terfilter),
   - kartu "Tema Kepmen terbanyak" = "Pengabdian dan Pengembangan Masyarakat" (basis **seluruh
     UGM**, tanpa angka, jadi tidak terlihat sebagai angka UGM),
   - kartu `overview` dampak = 148 / 155 / 255 → jumlahnya 558, **bukan 383**,
   - narasi eksekutif menyebut "UGM mencatat **383** berita dampak ... Pengabdian ... **136**
     berita" — dua basis berbeda dalam satu paragraf.
   Ini bukan bug baru (dashboard lama sama), tapi di versi baru angka-angka ini berdekatan sehingga
   mudah terbaca sebagai satu basis. `narasi_logic.generate_executive_summary` sudah punya
   parameter `scope_label` (default "UGM") yang memang dibuat untuk kasus ini — `page_dampak.py`
   belum memakainya, dan `story.py` juga belum. Saran minimal: isi `scope_label` (mis. "hasil
   filter unit kerja") + keterangan kecil pada kartu "Tema Kepmen terbanyak".
3. **Format angka campur** (klaim Anda benar): metrik "19.829" (titik), insight "12.534" dan
   "7,405" (koma), persen "57.9%"/"1.1%" (titik). Terverifikasi di UI. Konsisten dengan dashboard
   lama, tapi untuk versi baru sebaiknya diseragamkan (id-ID: titik ribuan, koma desimal).
4. **Kalimat "pertumbuhan" saat angkanya turun.** Dengan filter Fakultas Farmasi muncul:
   "Dampak Lingkungan mencatat pertumbuhan tercepat, tumbuh **-22.2%**". Kata "pertumbuhan" +
   tanda minus saling bertabrakan. Ini juga ada di narasi lama, tapi mudah diperbaiki
   ("penurunan terbesar" bila negatif).
5. **Narasi eksekutif memakai angka tingkat universitas walau scope-nya sudah difilter.** Karena
   `scope_label` default "UGM" dan `b`/`t` tidak difilter, kalimat "UGM mencatat 383 berita dampak
   yang tersebar di tiga dampak" bisa terbaca sebagai angka UGM padahal itu angka hasil filter.
   `narasi_logic.py` sudah menyediakan `scope_label` — sebaiknya diisi (mis. "hasil filter") untuk
   kasus berfilter.
6. **Label heatmap panjang**: baris "Konsumsi yang Bertanggung Jawab" membungkus 2 baris dan
   kolom tahun terakhir terpotong di kartu yang sempit (scroll horizontal tersedia, tapi tidak
   kentara). Pertimbangkan `min-width` kolom atau tanda "geser →".
7. **Timestamp mentah** di hero & footer: "Data terakhir: 2026-09-15T00:44:34+00:00" — sebaiknya
   diformat ("15 September 2026, 00.44 WIB").
8. **Judul kartu "SDGs"** di Bagian I hanya berbunyi "SDGs"; keterangan "pencocokan langsung URL
   sitemap" sudah ada di caption, tapi tidak di kartu jalur — boleh diringkas ke kartu juga.

---

## 6. Risiko sebelum dipakai di server Yayan

1. **Rute bersih di produksi.** `web/src/main.tsx` memakai `BrowserRouter` tanpa
   `createBrowserRouter`; dev server Vite sudah menangani fallback SPA, tetapi build statis yang
   disajikan nginx hanya aman karena ada `try_files $uri $uri/ /index.html` (ada di
   `deploy/nginx.conf`) — pastikan konfigurasi itu yang dipakai, kalau tidak `/dampak` → 404.
2. **URL API di produksi.** `web/src/lib/api.ts:22` memakai `BASE_URL + 'api/v1'`; di subpath
   `/analytics/` ini menjadi `/analytics/api/v1`, dan `deploy/edge-nginx.conf.template` sudah
   memetakan `location /analytics/api/` → `web:8080/api/` → `api:8000`. Rantai ini konsisten —
   bagus, tinggal diuji di Postgres.
3. **Uji di Postgres belum ada.** Semua verifikasi di sesi ini memakai MySQL lokal (klaim Anda
   benar). Karena §4.1 justru soal perbedaan dialek, uji Postgres sebaiknya dijalankan sebelum
   merge — terutama endpoint `/news` dengan filter SDG, dan `accreditation` yang ORDER BY-nya
   sudah dialek-aware.
4. **PR, bukan push langsung ke main.** Setuju dengan rencana Anda: `web/` dan `api/` adalah
   wilayah kerja Yayan. Branch `putri.update` sudah ter-push (a41447f) — buka PR ke `main` setelah
   §4.1–4.3 dibereskan.
5. **`web/dist/` hasil build tidak ter-track git** (bagus, tidak mengotori repo). Namun perintah
   `npm run build` dijalankan sebelum `npm ci` tidak apa-apa — `.bat` sudah memakai `npm ci` saat
   `node_modules` belum ada.
6. **`.venv` root dipakai `.bat`** (bukan `venv`): saat ini `.venv` berisi FastAPI/uvicorn/pytest
   sedangkan `venv` berisi pandas/plotly/streamlit. Dua venv berdampingan itu sah, tapi mudah
   tertukar — catat di README agar tidak membingungkan.

---

## 7. Perintah yang saya pakai (bisa Anda ulangi)

```bash
# angka live
./venv/Scripts/python.exe -c "..."          # lihat skill ugm-analytics: kueri MySQL via SQLAlchemy

# API
curl -s "http://127.0.0.1:8000/api/v1/analytics/story?mode=impact&pillar=Lingkungan&year_from=2004&year_to=2026"
curl -s -o /dev/null -w '%{http_code}\n' "http://127.0.0.1:8000/api/v1/analytics/news?mode=impact&sdgs=13"   # 503

# test
cd api && ../.venv/Scripts/python.exe -m pytest tests -q                      # 1 failed, 19 passed
cd api && ../.venv/Scripts/python.exe -m pytest tests/test_story.py -q        # 14 passed

# build web
cd web && npm run build
```

UI diuji headless dengan Edge (`C:\Program Files (x86)\Microsoft\Edge\Application\msedge.exe`)
via puppeteer-core; skrip ada di `D:\ugm-review-tmp\*.mjs`, screenshot di folder yang sama.

---

## 8. Daftar kerja yang saya sarankan (urut prioritas)

1. ~~Perbaiki `/analytics/news` filter SDG di MySQL~~ — **selesai 2026-09-21** (§4.1).
2. ~~Rapikan isolasi test `test_postgres_config`~~ — **selesai 2026-09-21** (§4.2).
3. ~~Perbaiki cache `StoryService`~~ — **selesai 2026-09-21** (§4.3).
4. ~~Sembunyikan label rail pada lebar < 1500px~~ — **selesai 2026-09-21** (§5.1).
5. Tambah keterangan cakupan pada metrik/narasi saat filter non-default aktif — §5.2 & §5.5.
6. Seragamkan format angka id-ID dan perbaiki kalimat "pertumbuhan -22.2%" — §5.3 & §5.4.
7. Jalankan sekali di Postgres (Yayan), lalu buka PR ke `main` — §6.

Sisa yang belum dikerjakan (5–7) sengaja tidak saya sentuh: dua di antaranya mengubah **angka
yang dilihat pengguna**, jadi butuh keputusan Anda dulu (basis hitungan mana yang benar), bukan
keputusan teknis yang bisa saya ambil sendiri.

---

## 9. Integrasi fitur dashboard lama → web baru (permintaan 2026-09-21)

### 9.1 Tombol "Masuk" di header dihapus
`web/src/shell.tsx`: tautan `.auth-link` ("Masuk") dihapus. Login hanya lewat gerbang portal
Akreditasi, jadi tidak ada dua pintu yang membingungkan. Saat sudah login, header menampilkan
nama pengguna (tautan ke `/profil`) dan lencana **Admin** (tautan ke `/admin`) bila berlaku,
plus tombol "Keluar".

### 9.2 Profil Saya & Admin diintegrasikan (padanan `page_profil.py` + `page_admin.py`)
Endpoint API baru (butuh login):

| Endpoint | Isi |
|---|---|
| `GET /api/v1/analytics/accreditation/profile` | identitas akun, statistik, pekerjaan berjalan, riwayat laporan |
| `GET /api/v1/analytics/accreditation/admin/users` | ringkasan + seluruh akun (khusus admin) |
| `POST /api/v1/analytics/accreditation/admin/users/{id}/action` | `blokir` / `admin` / `hapus` |

Halaman web baru: `/profil` dan `/admin` (`web/src/account.tsx`). Isinya mengikuti dashboard lama:
- **Profil**: nama, email, terdaftar sejak, login terakhir; kartu statistik (dokumen digenerate,
  diupload, pekerjaan berjalan, riwayat); kartu **Sedang dikerjakan** (prodi × LED/LKPS + progress
  kelengkapan + tombol **Lanjutkan** yang membuka `/akreditasi?prodi=…&dokumen=…`); tabel
  **Riwayat dokumen**.
- **Admin**: kartu ringkasan (total akun, admin, diblokir), tabel semua akun, dan kartu aksi per
  akun (Blokir/Buka blokir, Jadikan/Cabut admin, Hapus dengan konfirmasi). Tombol untuk akun
  sendiri dinonaktifkan + diberi `title` penjelas.

Keamanan (mengikuti `akun_akreditasi.py`): setiap aksi **dicek ulang di server** — pelaku harus
admin aktif di DB, dan tidak boleh menyentuh akunnya sendiri. Menyembunyikan menu di UI saja tidak
dianggap pengamanan.

Yang **tidak** dipindah (dan sebaiknya tidak dipaksa): unduhan file laporan Word dari riwayat.
Berkas `.docx` ada di disk mesin ini (`akreditasi/data/generated/...`), sedangkan server API tidak
mengelola berkas itu — di produksi pun berbeda container. Riwayat tetap menampilkan daftar lengkap.

### 9.3 Verifikasi yang dijalankan
- `pytest tests` → **35 passed** (dari 20 sebelumnya; uji baru `test_accreditation_account.py` (11),
  `test_sqlcompat.py` (3), `test_db_error_message.py` (1) — semuanya pakai SQLite sementara).
- `npm run build` + `npx tsc -b` → lolos.
- UI diuji headless (Edge + puppeteer): header tanpa "Masuk"; login admin → chip nama + Admin;
  `/profil` menampilkan 4 kartu identitas, 1 pekerjaan berjalan (14/25 = 56%), 1 riwayat;
  tombol Lanjutkan membuka `/akreditasi?prodi=mei&dokumen=LED` dengan pilihan benar; `/admin`
  menampilkan 2 akun dengan 3 tombol nonaktif untuk akun sendiri; blokir → "diblokir", buka blokir →
  "dibuka"; non-admin ditolak ("Akses ditolak — halaman ini khusus admin"); pengunjung anonim
  dialihkan ke `/akreditasi`, dan setelah login dikembalikan ke `/admin`; mode gelap & lebar 390px
  tanpa overflow.
- **MySQL asli tidak tersentuh**: pengujian UI memakai API SQLite sementara di `%TEMP%`
  (skrip + file DB sudah dihapus). Setelah semua selesai, MySQL dicek ulang: 2 akun, 0 sesi,
  118 baris `data_manual` — sama seperti sebelum pengujian.

### 9.4 Selector Fakultas & Program Studi dipisah (permintaan lanjutan)
Sebelumnya satu dropdown gabungan "Fakultas & Program Studi" berisi 18 baris "Fakultas — Prodi".
Sekarang dua dropdown berjenjang, mengikuti alur dashboard lama
(`akreditasi/scripts/dashboard_render.py` → `render_prodi_selector`):

| Dropdown | Isi | Perilaku |
|---|---|---|
| **Fakultas (wajib)** | 20 fakultas, diurutkan nama | menandai isinya: "(18 prodi)" atau "(belum ada prodi)"; ada keterangan kecil di bawahnya |
| **Program Studi (wajib)** | hanya prodi milik fakultas terpilih | **terkunci** sampai fakultas dipilih; ganti fakultas → otomatis ke prodi pertama |
| **Dokumen** | LED / LKPS | tidak berubah |

Detail perilaku:
- Tombol **Lanjutkan** dari Profil (`?prodi=…`) tetap bekerja: fakultas ikut tersinkron ke prodi itu.
- Prodi tanpa `fakultas_id` tidak lagi hilang diam-diam — muncul pemberitahuan (tidak memblokir portal).
- Label jenjang tidak diulang bila sudah terkandung di nama prodi ("Doktor Ilmu Fisika", bukan
  "Doktor Ilmu Fisika — Doktor").
- Kolom Fakultas dibuat lebih lebar (2.1fr) karena nama fakultas UGM panjang; teks terbaca penuh
  (diukur 507px, tanpa elipsis).

**Temuan dari data nyata** (MySQL `ugm_analytics`): 20 fakultas tetapi hanya 18 prodi, dan ke-18 prodi
itu semuanya di bawah `fakultas_id = 8` (MIPA). 19 fakultas lain belum punya prodi sama sekali.
Ini terlihat jelas setelah pemisahan dropdown — sebelumnya tersamar karena semuanya satu daftar.
Bila prodi fakultas lain memang sudah ada, datanya perlu diisi di tabel `akreditasi_prodi`.

Verifikasi: UI headless 12/12 lulus dengan bentuk data yang **sama persis** dengan MySQL (20 fakultas,
18 prodi di MIPA) yang direplikasi ke SQLite sementara — MySQL asli tidak ditulis. `pytest` 35 passed,
`tsc -b` bersih, `npm run build` lolos.
