> **Arsip (dipindah ke `deploy/legacy/` 2026-09-21):** isi asli `deploy/README.md` sebelum merge `dev.yayan`
> (deployment Streamlit + MySQL). Disimpan agar info koneksi lama tidak hilang. Jalur deploy yang
> AKTIF sekarang `deploy/compose.yml` + `deploy/README.md` (Postgres + api + web + edge nginx).

# Deploy — UGM Impact Analytics

> Konfigurasi deploy penuh (image aplikasi, Cloudflare Tunnel, dsb.) dikelola
> tim infra (BTD/Hermes) di server NUC, kemungkinan dari repo terpisah. File
> ini mendokumentasikan bagian yang berubah karena migrasi database dari
> DuckDB ke MySQL — lihat `deploy/legacy/migrasi_duckdb_ke_mysql.py` (dulu di root).

## Database MySQL

Database MySQL berjalan sebagai container terpisah bernama `mysql` dalam
docker-compose yang sama (lihat `deploy/legacy/docker-compose.mysql.yml`, dulu `docker-compose.yml` di root).
Service aplikasi (dashboard/Streamlit) harus berada di network Docker yang
sama supaya bisa terkoneksi ke database lewat nama service — host `mysql`,
bukan `localhost`. Kredensial diambil dari `.env` di root project (lihat
`.env.example` untuk daftar variabel yang dibutuhkan: `MYSQL_HOST`,
`MYSQL_PORT`, `MYSQL_USER`, `MYSQL_PASSWORD`, `MYSQL_DB`,
`MYSQL_ROOT_PASSWORD`).

## Deploy pertama kali — import dump database

Untuk deploy pertama kali, import dump database dari file
`ugm_analytics_dump.sql` (arsip: `D:\ugm-analytics-arsip\database\`) ke dalam container MySQL menggunakan:

```
docker exec -i <nama_container_mysql> mysql -u root -p ugm_analytics < ugm_analytics_dump.sql
```

Ganti `<nama_container_mysql>` dengan nama/ID container MySQL yang sedang
berjalan (`docker ps` untuk melihatnya).
