"""Sinkronisasi tabel DuckDB berita-dampak ke MySQL (prefix "berita_").

Step terakhir update_mingguan.py: setelah seluruh pipeline lokal
(backfill_sitemap -> ... -> tag_kepmen_all) selesai menulis ke
data/ugm_news.duckdb, script ini me-replace tabel berita_* di MySQL supaya
dashboard (yang baca dari MySQL, lihat dashboard_berita_dampak.py) melihat
data terbaru. Logikanya sama dengan migrasi_ke_mysql.py di root project,
di-replace penuh per tabel (if_exists="replace") -- idempoten, aman
dijalankan ulang.

Kredensial MySQL dibaca dari .env di root project (MYSQL_HOST/PORT/USER/
PASSWORD/DB). Kalau belum diisi, sync dilewati (data tetap tersimpan di
DuckDB, tidak menggagalkan pipeline).

Jalankan (dari folder berita-dampak):
  python scripts/sync_mysql.py
"""

from pathlib import Path

import duckdb
import os
from dotenv import load_dotenv

ROOT = Path(__file__).resolve().parents[1]
DB_PATH = ROOT / "data" / "ugm_news.duckdb"
PREFIX = "berita_"

load_dotenv(ROOT.parent / ".env")

REQUIRED_ENV = ("MYSQL_HOST", "MYSQL_PORT", "MYSQL_USER", "MYSQL_PASSWORD", "MYSQL_DB")


def main() -> None:
    missing = [k for k in REQUIRED_ENV if not os.environ.get(k)]
    if missing:
        print(f"[SKIP] Env MySQL belum lengkap ({', '.join(missing)}) -- "
              f"lewati sync, data tetap ada di DuckDB.")
        return

    from sqlalchemy import create_engine

    url = (
        f"mysql+pymysql://{os.environ['MYSQL_USER']}:{os.environ['MYSQL_PASSWORD']}"
        f"@{os.environ['MYSQL_HOST']}:{os.environ['MYSQL_PORT']}/{os.environ['MYSQL_DB']}"
    )
    engine = create_engine(url)
    with engine.connect() as conn:
        conn.exec_driver_sql("SELECT 1")

    con = duckdb.connect(str(DB_PATH), read_only=True)
    tables = con.execute("SHOW TABLES").fetchdf()["name"].tolist()
    for t in tables:
        df = con.execute(f"SELECT * FROM {t}").fetchdf()
        nama_tabel = f"{PREFIX}{t}"
        df.to_sql(nama_tabel, engine, if_exists="replace", index=False, chunksize=1000)
        print(f"  [OK] {t} -> {nama_tabel} ({len(df)} baris)")
    con.close()
    print(f"SELESAI sync ke MySQL ({len(tables)} tabel).")


if __name__ == "__main__":
    main()
