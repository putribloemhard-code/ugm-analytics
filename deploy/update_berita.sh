#!/usr/bin/env sh
# Update berita mingguan di server: pipeline ke mysql-reader, lalu sinkron tabel berita ke PostgreSQL.
#
# Pakai (dari folder deploy/):   sh update_berita.sh
# Otomatis tiap Sabtu 06:00 (crontab -e):
#   0 6 * * 6 cd /path/ke/ugm-analytics/deploy && sh update_berita.sh >> ../runtime/update_berita.log 2>&1
#
# Tag manual dari web (berita_sdg_manual, berita_tema_manual) TIDAK disentuh: sinkron hanya mengganti
# tabel berita_* hasil pipeline, dalam satu transaksi. Kalau pipeline gagal, sinkron tidak dijalankan
# dan dashboard tetap memakai data minggu lalu.
set -eu

cd "$(dirname "$0")"
COMPOSE="docker compose --env-file .env -f compose.yml"

echo "[$(date '+%F %T')] mulai update berita"
# Pastikan mysql-reader menyala (restart: "no", jadi bisa mati setelah server reboot).
$COMPOSE up -d mysql-reader

echo "[$(date '+%F %T')] pipeline: ambil + tagging berita baru"
$COMPOSE --profile pipeline run --rm --build pipeline

echo "[$(date '+%F %T')] sinkron tabel berita ke PostgreSQL (tag manual dilewati)"
$COMPOSE run --rm --no-deps --entrypoint python api /app/migrate_mysql_to_postgres.py --sinkron-berita

echo "[$(date '+%F %T')] selesai"
