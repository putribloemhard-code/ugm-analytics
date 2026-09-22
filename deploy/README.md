# Paket Deploy Terisolasi — UGM Analytics

Paket ini menjalankan frontend React/Vite, FastAPI read-only, dan MySQL baru dalam satu Compose project terisolasi. Ia tidak menyentuh stack, container, volume, proxy, database, atau data aplikasi lain di BTD.

## Batas dan asumsi

- State runtime disimpan di `../runtime/` (di luar repo, gitignored): `runtime/postgres`,
  `runtime/mysql-reader-v2`, `runtime/accreditation-uploads`. Ia dimulai kosong dan tidak menyentuh
  data stack lain.
- Agar analytics memuat data nyata, operator harus menyetujui dan menyediakan dump MySQL yang kompatibel sebagai artefak terpisah di `../migration-input/analytics.reader.sql`. Dump tidak boleh dimasukkan ke image, source archive, atau Git.
- Tidak ada IP/domain yang ditanam di Dockerfile, Nginx, Compose, atau kode frontend. URL publik dan CORS dipasok saat runtime melalui `deploy/.env`.
- `PUBLIC_ORIGIN` harus tepat sama dengan origin browser yang disetujui, misalnya `https://analytics.example.ac.id` atau `http://hostname:port`; tanpa trailing slash.
- Secara default `UGM_ANALYTICS_BIND_ADDRESS=127.0.0.1`, sehingga aplikasi hanya siap untuk proxy lokal. Membuka ke LAN harus keputusan eksplisit dengan mengganti nilai env tersebut; tidak perlu mengubah source.
- Nginx menyajikan SPA dan meneruskan `/api/` ke FastAPI dalam jaringan internal. Karena itu `VITE_API_BASE_URL` tetap relatif (`/analytics/api/v1` untuk topologi edge bawaan), portable, dan tidak membutuhkan hardcoded host/IP.

## Isi paket

- `compose.yml` — Compose isolated: `postgres`, `mysql-reader`, `api`, `web`, `edge`.
- `api.Dockerfile` — FastAPI + modul domain yang diperlukan dari pipeline berita.
- `web.Dockerfile` — build statis React/Vite dan runtime Nginx.
- `nginx.conf` — SPA fallback, `/api/` proxy internal, dan health endpoint.
- `.env.example` — kontrak environment target tanpa secret nyata.
- `legacy/` — file jalur lama yang SUDAH tidak dipakai: `docker-compose.mysql.yml` (MySQL-only, dulu di root), `migrasi_duckdb_ke_mysql.py` (dulu `migrasi_ke_mysql.py` di root), `README-streamlit-mysql.md` (arsip deploy Streamlit + MySQL). Disimpan untuk jejak; jangan dijalankan sebagai paket deploy.

## Kontrak environment

Salin `.env.example` menjadi `.env` hanya pada host target, mode `0600`, lalu isi nilai final.
Compose memakai sintaks `${VAR:?pesan}` untuk SEMUA variabel, jadi `.env` yang kurang/kosong
**menggagalkan `docker compose config` dan `up` dengan pesan yang menyebut variabelnya** — bukan
lagi warning "Defaulting to a blank string" yang berujung postgres gagal boot tanpa sebab jelas.

- `COMPOSE_PROJECT_NAME` — namespace Docker. Jangan gunakan nama stack aktif.
- `UGM_ANALYTICS_BIND_ADDRESS` dan `UGM_ANALYTICS_PORT` — listener host tanpa mengubah Compose.
  Nilai `.env.example` (`127.0.0.1`) adalah pilihan aman untuk proxy lokal; membuka ke LAN harus
  keputusan eksplisit dengan menggantinya (mis. `0.0.0.0`).
- `PUBLIC_ORIGIN` — origin eksternal yang diizinkan CORS oleh FastAPI.
- `VITE_API_BASE_URL` dan `VITE_APP_BASE_PATH` — base API dan base path SPA yang dikompilasi ke
  bundle; gunakan `/analytics/api/v1` dan `/analytics/` untuk topologi bawaan (edge nginx).
- `POSTGRES_DB`, `POSTGRES_USER`, `POSTGRES_PASSWORD` — database PostgreSQL tujuan; dibuat saat
  inisialisasi pertama.
- `SOURCE_MYSQL_DB`, `SOURCE_MYSQL_USER`, `SOURCE_MYSQL_PASSWORD`, `SOURCE_MYSQL_ROOT_PASSWORD` —
  container `mysql-reader` yang memuat dump sumber untuk migrasi awal.

Perubahan credential setelah volume terinisialisasi tidak memperbarui password database secara
otomatis (image resmi hanya menjalankan `initdb` saat direktori data kosong). Untuk database
eksperimen baru, finalkan environment sebelum lifecycle pertama.

`mysql-reader` memasang `../migration-input/analytics.reader.sql` sebagai
`/docker-entrypoint-initdb.d/analytics.sql` dengan mode read-only. Karena itu:

- folder `migration-input/` dan dump di dalamnya **wajib ada sebelum `up` pertama**; keduanya
  gitignored dan disiapkan operator di server, bukan diambil dari repo;
- kalau volume `runtime/mysql-reader-v2` sudah terisi dari `up` sebelumnya, skrip init di
  `docker-entrypoint-initdb.d` **tidak dijalankan ulang** — isi ulang dump berarti
  `docker compose down -v` (menghapus volume) atau impor manual lewat `stdin`.

## Gate pra-deploy

1. Verifikasi remote workspace belum ada dan port yang dipilih belum dipakai.
2. Transfer source terfilter tanpa `.env`, `.git`, `node_modules`, `dist`, cache Python, dump, atau runtime data.
3. Cocokkan SHA-256 manifest lokal vs remote.
4. Operator membuat `deploy/.env` di target dengan permission `0600` dan secret baru; jangan kirim/print secret lewat chat.
5. Jalankan hanya validasi konfigurasi:

   `docker compose --env-file deploy/.env -f deploy/compose.yml config -q`

6. Review hasil validasi dan import-dump plan terlebih dahulu. Build/up, proxy routing, import dump, dan pembukaan listener adalah lifecycle actions terpisah yang memerlukan persetujuan eksplisit.

## Setelah lifecycle diizinkan

Urutan aman yang direncanakan:

1. Pastikan `../migration-input/analytics.reader.sql` sudah ada (kalau belum, `up` akan gagal di
   `mysql-reader` karena bind mount menunjuk ke path yang tidak ada).
2. Build image `api` dan `web`.
3. Start project ini saja; `postgres` dan `mysql-reader` memakai volume di `../runtime/` milik proyek sendiri.
4. Tunggu healthcheck `postgres`, `mysql-reader`, `api`, `web`, lalu `edge`.
5. Probe `http://<bind-address>:<port>/analytics/` (SPA), `/analytics/api/v1/...`, dan
   `http://127.0.0.1:8000/healthz` dari dalam jaringan internal.
6. Verifikasi tidak ada container/volume/network proyek lain yang berubah.

## Migrasi MySQL → PostgreSQL

`deploy/migrate_mysql_to_postgres.py` menyalin tabel MySQL sumber ke PostgreSQL dalam container
`api` (skripnya ada di `/app/migrate_mysql_to_postgres.py`, image sudah memuat `pandas`,
`pymysql`, dan `psycopg`). Env yang dibaca: `SOURCE_MYSQL_{HOST,PORT,USER,PASSWORD,DB}` dan
`POSTGRES_{HOST,PORT,USER,PASSWORD,DB}` — jadi jalankan dari dalam jaringan internal, mis.:

    docker compose -f deploy/compose.yml run --rm --entrypoint python api \
      /app/migrate_mysql_to_postgres.py

Skrip menolak berjalan kalau PostgreSQL tujuan sudah berisi `berita_berita` (proteksi overwrite),
dan setelah selesai membuat indeks `berita_berita(tanggal)`, `berita_berita_kepmen_all(url)`,
`berita_sitemap_sdg(url)`, `berita_unit_kerja(url)`. Karena `mysql-reader` sudah memuat dump yang
sama, langkah ini hanya perlu kalau data diambil langsung dari MySQL sumber.

## Pemulihan: WARN "variable is not set" + postgres unhealthy

Gejala di host target: `docker compose up` mencetak deretan
`WARN[0000] The "POSTGRES_PASSWORD" variable is not set. Defaulting to a blank string.` lalu
container `postgres` gagal/berhenti. Penyebabnya hampir selalu `deploy/.env` belum ada atau belum
lengkap; `docker compose` mencari `.env` di direktori kerja, bukan di folder file compose.

Setelah perubahan di atas, gejala itu tidak lagi mungkin terjadi: compose langsung berhenti dengan
pesan `POSTGRES_PASSWORD belum diisi di deploy/.env`. Urutan pemulihan dari volume yang sudah
setengah terinisialisasi:

1. `cd <root proyek>/deploy` lalu `cp .env.example .env && chmod 600 .env`; isi semua nilai.
2. `docker compose config -q` — harus keluar tanpa error dan tanpa WARN.
3. `docker compose down -v` lalu `rm -rf ../runtime/postgres/*` — WAJIB, karena direktori data
   PostgreSQL yang gagal inisialisasi tidak bisa dipakai ulang (`initdb` tidak mengulang).
4. `docker compose up -d`, lalu `docker compose ps` dan `docker compose logs postgres`.
5. `docker compose exec postgres pg_isready -U <POSTGRES_USER> -d <POSTGRES_DB>`.

## Catatan data

Tanpa import database, endpoint API yang membutuhkan tabel `berita_*` akan tidak tersedia. Ini expected; healthcheck FastAPI tetap hanya memeriksa proses, bukan ketersediaan data analytics. Jangan menyatakan aplikasi siap dipakai sebelum dump, schema, dan query read-only terhadap tabel yang diperlukan tervalidasi.
