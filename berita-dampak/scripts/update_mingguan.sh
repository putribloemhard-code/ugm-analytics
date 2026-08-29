#!/bin/bash
# Wrapper untuk cron mingguan: jalankan update pipeline, simpan log, cetak ringkasan.
cd "$(dirname "$0")/.."

# Resolve interpreter Python: env var override > venv Linux > venv Windows (dev) > PATH.
if [ -n "$UGM_ANALYTICS_PYTHON" ]; then
  PY="$UGM_ANALYTICS_PYTHON"
elif [ -x "../venv/bin/python" ]; then
  PY="../venv/bin/python"
elif [ -x "../venv/Scripts/python.exe" ]; then
  PY="../venv/Scripts/python.exe"
else
  PY="python3"
fi

LOG=logs_update_mingguan.txt
echo "=== $(date '+%Y-%m-%d %H:%M:%S') mulai ===" >> "$LOG"
"$PY" scripts/update_mingguan.py >> "$LOG" 2>&1
RC=$?
echo "=== selesai exit=$RC $(date '+%H:%M:%S') ===" >> "$LOG"
if [ $RC -ne 0 ]; then
  echo "UPDATE GAGAL (exit $RC) — cek $LOG"
  exit $RC
fi
# Ringkasan untuk delivery
N=$("$PY" -c "import duckdb; c=duckdb.connect('data/ugm_news.duckdb', read_only=True); print(c.execute('SELECT COUNT(*) FROM berita').fetchone()[0]); c.close()" 2>/dev/null)
echo "Update berita-dampak selesai. Total berita di DB: $N"
