"""Cetak jumlah baris di tabel berita_berita (dipakai update_mingguan.sh
untuk ringkasan log cron)."""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from db import get_engine, t  # noqa: E402

if __name__ == "__main__":
    engine = get_engine()
    with engine.connect() as conn:
        n = conn.exec_driver_sql(f"SELECT COUNT(*) FROM `{t('berita')}`").scalar()
    print(n)
