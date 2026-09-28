#!/usr/bin/env sh
# Backup harian UGM Analytics: database PostgreSQL + berkas akreditasi (unggahan dan Word hasil generate).
#
# Pakai (dari folder deploy/):   sh backup.sh
# Otomatis tiap malam (crontab -e):
#   30 1 * * * cd /path/ke/ugm-analytics/deploy && sh backup.sh >> ../runtime/backup.log 2>&1
#
# Hasil: ../backups/<tanggal>/ berisi postgres.sql.gz dan akreditasi-files.tar.gz.
# Backup yang lebih tua dari SIMPAN_HARI (bawaan 14) dihapus otomatis.
# Pulihkan database:  gunzip -c postgres.sql.gz | docker compose exec -T postgres psql -U "$POSTGRES_USER" -d "$POSTGRES_DB"
set -eu

cd "$(dirname "$0")"
SIMPAN_HARI="${SIMPAN_HARI:-14}"
TUJUAN="../backups/$(date +%Y-%m-%d_%H%M)"
mkdir -p "$TUJUAN"

# Kredensial dibaca dari deploy/.env yang sama dengan docker compose.
set -a
. ./.env
set +a

echo "[$(date '+%F %T')] backup database ke $TUJUAN"
docker compose exec -T postgres pg_dump -U "$POSTGRES_USER" -d "$POSTGRES_DB" --no-owner --clean --if-exists \
  > "$TUJUAN/postgres.sql"
# Dump ke file dulu, bukan pipa ke gzip: tanpa pipefail, pg_dump yang gagal tidak akan terdeteksi.
# Dump kosong = gagal diam-diam; hentikan dengan galat supaya terlihat di log cron.
if [ ! -s "$TUJUAN/postgres.sql" ]; then
  echo "GAGAL: dump database kosong" >&2
  exit 1
fi
gzip "$TUJUAN/postgres.sql"

echo "[$(date '+%F %T')] backup berkas akreditasi"
ADA=""
for d in accreditation-uploads accreditation-generated; do
  if [ -d "../runtime/$d" ]; then ADA="$ADA $d"; fi
done
if [ -n "$ADA" ]; then
  # shellcheck disable=SC2086 -- daftar folder sengaja dipecah per spasi
  tar -czf "$TUJUAN/akreditasi-files.tar.gz" -C ../runtime $ADA
fi

find ../backups -mindepth 1 -maxdepth 1 -type d -mtime +"$SIMPAN_HARI" -exec rm -rf {} +
echo "[$(date '+%F %T')] selesai: $(du -sh "$TUJUAN" | cut -f1)"
