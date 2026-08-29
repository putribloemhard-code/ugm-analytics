# Deploy — UGM Impact Analytics

> Konfigurasi deploy penuh (image aplikasi, Cloudflare Tunnel, dsb.) dikelola
> tim infra (BTD/Hermes) di server NUC, kemungkinan dari repo terpisah. File
> ini mendokumentasikan bagian yang berubah karena migrasi database dari
> DuckDB ke MySQL — lihat `migrasi_ke_mysql.py` di root project.

## Database MySQL

Database MySQL berjalan sebagai container terpisah bernama `mysql` dalam
docker-compose yang sama (lihat `docker-compose.yml` di root project).
Service aplikasi (dashboard/Streamlit) harus berada di network Docker yang
sama supaya bisa terkoneksi ke database lewat nama service — host `mysql`,
bukan `localhost`. Kredensial diambil dari `.env` di root project (lihat
`.env.example` untuk daftar variabel yang dibutuhkan: `MYSQL_HOST`,
`MYSQL_PORT`, `MYSQL_USER`, `MYSQL_PASSWORD`, `MYSQL_DB`,
`MYSQL_ROOT_PASSWORD`).

## Deploy pertama kali — import dump database

Untuk deploy pertama kali, import dump database dari file
`ugm_analytics_dump.sql` ke dalam container MySQL menggunakan:

```
docker exec -i <nama_container_mysql> mysql -u root -p ugm_analytics < ugm_analytics_dump.sql
```

Ganti `<nama_container_mysql>` dengan nama/ID container MySQL yang sedang
berjalan (`docker ps` untuk melihatnya).
