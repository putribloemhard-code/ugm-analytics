# Paket Deploy Terisolasi — UGM Analytics

Paket ini menjalankan frontend React/Vite, FastAPI read-only, dan MySQL baru dalam satu Compose project terisolasi. Ia tidak menyentuh stack, container, volume, proxy, database, atau data aplikasi lain di BTD.

## Batas dan asumsi

- Database `data/mysql` dimulai kosong. Pipeline berita, database lama, dan dashboard Streamlit tidak ikut dipindahkan oleh paket ini.
- Agar analytics memuat data nyata, operator harus menyetujui dan menyediakan dump MySQL yang kompatibel sebagai artefak terpisah. Dump tidak boleh dimasukkan ke image, source archive, atau Git.
- Tidak ada IP/domain yang ditanam di Dockerfile, Nginx, Compose, atau kode frontend. URL publik dan CORS dipasok saat runtime melalui `deploy/.env`.
- `PUBLIC_ORIGIN` harus tepat sama dengan origin browser yang disetujui, misalnya `https://analytics.example.ac.id` atau `http://hostname:port`; tanpa trailing slash.
- Secara default `UGM_ANALYTICS_BIND_ADDRESS=127.0.0.1`, sehingga aplikasi hanya siap untuk proxy lokal. Membuka ke LAN harus keputusan eksplisit dengan mengganti nilai env tersebut; tidak perlu mengubah source.
- Nginx menyajikan SPA dan meneruskan `/api/` ke FastAPI dalam jaringan internal. Karena itu `VITE_API_BASE_URL=/api/v1` adalah relatif, portable, dan tidak membutuhkan hardcoded host/IP.

## Isi paket

- `compose.yml` — Compose isolated: `mysql`, `api`, `web`.
- `api.Dockerfile` — FastAPI + modul domain yang diperlukan dari pipeline berita.
- `web.Dockerfile` — build statis React/Vite dan runtime Nginx.
- `nginx.conf` — SPA fallback, `/api/` proxy internal, dan health endpoint.
- `.env.example` — kontrak environment target tanpa secret nyata.
- `legacy/` — file jalur lama yang SUDAH tidak dipakai: `docker-compose.mysql.yml` (MySQL-only, dulu di root), `migrasi_duckdb_ke_mysql.py` (dulu `migrasi_ke_mysql.py` di root), `README-streamlit-mysql.md` (arsip deploy Streamlit + MySQL). Disimpan untuk jejak; jangan dijalankan sebagai paket deploy.

## Kontrak environment

Salin `.env.example` menjadi `.env` hanya pada host target, mode `0600`, lalu isi nilai final:

- `COMPOSE_PROJECT_NAME` — namespace Docker. Jangan gunakan nama stack aktif.
- `UGM_ANALYTICS_BIND_ADDRESS` dan `UGM_ANALYTICS_PORT` — listener host tanpa mengubah Compose.
- `PUBLIC_ORIGIN` — origin eksternal yang diizinkan CORS oleh FastAPI.
- `VITE_API_BASE_URL` — base API yang dikompilasi ke bundle; gunakan `/api/v1` untuk topologi bawaan.
- `MYSQL_DB`, `MYSQL_USER`, `MYSQL_PASSWORD`, `MYSQL_ROOT_PASSWORD` — dibuat di target sebelum inisialisasi pertama.

Perubahan credential MySQL setelah `data/mysql` terinisialisasi tidak memperbarui password database secara otomatis. Untuk database eksperimen baru, finalkan environment sebelum lifecycle pertama.

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

1. Build image `api` dan `web`.
2. Start project ini saja; `mysql` menggunakan `deploy/data/mysql` milik proyek sendiri.
3. Jika disetujui, import dump kompatibel ke MySQL baru melalui stdin, bukan dengan menaruh dump ke source/image.
4. Tunggu healthcheck `mysql`, `api`, `web`.
5. Probe `http://<bind-address>:<port>/healthz`, SPA, dan `/api/v1/...` dari jalur publik yang benar.
6. Verifikasi tidak ada container/volume/network proyek lain yang berubah.

## Catatan data

Tanpa import database, endpoint API yang membutuhkan tabel `berita_*` akan tidak tersedia. Ini expected; healthcheck FastAPI tetap hanya memeriksa proses, bukan ketersediaan data analytics. Jangan menyatakan aplikasi siap dipakai sebelum dump, schema, dan query read-only terhadap tabel yang diperlukan tervalidasi.
