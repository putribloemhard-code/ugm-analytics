#!/bin/bash
# Wrapper untuk cron mingguan: jalankan update pipeline, simpan log, cetak ringkasan.
cd "$(dirname "$0")/.."
LOG=logs_update_mingguan.txt
echo "=== $(date '+%Y-%m-%d %H:%M:%S') mulai ===" >> "$LOG"
../venv/Scripts/python.exe scripts/update_mingguan.py >> "$LOG" 2>&1
RC=$?
echo "=== selesai exit=$RC $(date '+%H:%M:%S') ===" >> "$LOG"
if [ $RC -ne 0 ]; then
  echo "UPDATE GAGAL (exit $RC) — cek $LOG"
  exit $RC
fi
# Ringkasan untuk delivery
N=$(../venv/Scripts/python.exe -c "import duckdb; c=duckdb.connect('data/ugm_news.duckdb', read_only=True); print(c.execute('SELECT COUNT(*) FROM berita').fetchone()[0]); c.close()" 2>/dev/null)
echo "Update berita-dampak selesai. Total berita di DB: $N"
