"""Update berkala data berita-dampak (untuk cron mingguan / run manual).

Menjalankan seluruh pipeline berurutan, langsung baca/tulis MySQL (tabel
berprefix "berita_", lihat scripts/db.py -- tidak ada lagi DuckDB perantara):
  1. backfill_sitemap.py — ambil URL baru dari sitemap ugm.ac.id
  2. ingest.py          — ambil berita terbaru dari RSS (id + en)
  3. fetch_detail.py    — fetch detail URL sitemap yang belum ada di tabel berita
  4. normalisasi.py     — bersihkan teks + tanggal, dedup
  5. process_nlp.py     — tagging 4 topik inti (tabel berita_berita_topik)
  6. tag_kepmen_all.py       — tagging 14 tema Kepmen + SDG (tabel berita_berita_kepmen_all)
  7. tag_unit_kerja.py       — tagging 44 fakultas/sekolah/unit kerja UGM
                               (tabel berita_unit_kerja), independen dari tagging Kepmen
  8. generate_narasi_llm.py  — rangkai narasi ringkasan/insight pakai Gemini API,
                               cache ke MySQL (opsional -- skip aman kalau
                               GEMINI_API_KEY belum diisi, dashboard fallback
                               ke narasi template pandas)
  9. laporan_static.py       — regenerate laporan HTML statis

Semua script idempoten (INSERT IGNORE / replace tabel ringkasan), aman
dijalankan ulang. Jaringan dipakai untuk ugm.ac.id saja (bukan eLOK).

Lock file `data/.update_lock` mencegah dua update berjalan bersamaan
(tombol dashboard + cron). Kalau lock sudah ada, update dibatalkan.

Jalankan:
  python scripts/update_mingguan.py

Interpreter Python dipakai untuk tiap step diambil dari sys.executable
(interpreter yang menjalankan script ini), atau dari env var
UGM_ANALYTICS_PYTHON kalau di-set. Ini supaya pipeline jalan baik di
Windows (venv/Scripts/python.exe) maupun di container Linux (venv/bin/python).
"""

import os
import subprocess
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
PY = os.environ.get("UGM_ANALYTICS_PYTHON", sys.executable)
LOCK = ROOT / "data" / ".update_lock"

STEPS = [
    "backfill_sitemap.py",
    "ingest.py",
    "fetch_detail.py",
    "normalisasi.py",
    "process_nlp.py",
    "tag_kepmen_all.py",
    "tag_unit_kerja.py",
    "generate_narasi_llm.py",
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
