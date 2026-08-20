"""Update berkala data berita-dampak (untuk cron mingguan / run manual).

Menjalankan seluruh pipeline berurutan:
  1. backfill_sitemap.py — ambil URL baru dari sitemap ugm.ac.id
  2. ingest.py          — ambil berita terbaru dari RSS (id + en)
  3. fetch_detail.py    — fetch detail URL sitemap yang belum ada di tabel berita
  4. normalisasi.py     — bersihkan teks + tanggal, dedup
  5. process_nlp.py     — tagging 4 topik inti (tabel berita_topik)
  6. tag_kepmen_all.py  — tagging 13 topik Kepmen + SDG (tabel berita_kepmen_all)
  7. laporan_static.py  — regenerate laporan HTML statis

Semua script idempoten (INSERT OR IGNORE / CREATE OR REPLACE), aman dijalankan
ulang. Jaringan dipakai untuk ugm.ac.id saja (bukan eLOK).

Lock file `data/.update_lock` mencegah dua update berjalan bersamaan
(tombol dashboard + cron). Kalau lock sudah ada, update dibatalkan.

Jalankan:
  ../venv/Scripts/python.exe scripts/update_mingguan.py
"""

import os
import subprocess
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
PY = Path(__file__).resolve().parents[2] / "venv" / "Scripts" / "python.exe"
LOCK = ROOT / "data" / ".update_lock"

STEPS = [
    "backfill_sitemap.py",
    "ingest.py",
    "fetch_detail.py",
    "normalisasi.py",
    "process_nlp.py",
    "tag_kepmen_all.py",
    "laporan_static.py",
]


def main() -> None:
    if LOCK.exists():
        pid = LOCK.read_text().strip()
        print(f"UPDATE DIBATALKAN — update lain sedang berjalan (PID {pid}). "
              f"Tunggu sampai selesai lalu coba lagi.")
        sys.exit(2)

    LOCK.write_text(str(os.getpid()))
    t0 = time.time()
    print(f"=== UPDATE BERITA-DAMPAK mulai {time.strftime('%Y-%m-%d %H:%M:%S')} "
          f"(PID {os.getpid()}) ===", flush=True)
    rc = 0
    try:
        for step in STEPS:
            script = ROOT / "scripts" / step
            t1 = time.time()
            print(f"\n--- [{step}] ---", flush=True)
            r = subprocess.run(
                [str(PY), str(script)],
                cwd=str(ROOT),
                timeout=7200,  # 2 jam max (fetch_detail bisa lama saat pertama kali)
            )
            if r.returncode != 0:
                print(f"GAGAL {step} (exit {r.returncode})")
                rc = 1
                break
            print(f"  {step} selesai dalam {time.time()-t1:.0f} dtk", flush=True)
        print(f"\n=== SELESAI. Total waktu {time.time()-t0:.0f} dtk "
              f"(exit {rc}) ===", flush=True)
    finally:
        try:
            LOCK.unlink()
        except OSError:
            pass
    sys.exit(rc)


if __name__ == "__main__":
    main()
