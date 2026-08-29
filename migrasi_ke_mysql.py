"""
Migrasi data UGM Impact Analytics dari DuckDB (dan CSV) ke MySQL.

Jalankan dari root folder project:
       python migrasi_ke_mysql.py

"""

import duckdb
import pandas as pd
from pathlib import Path
from sqlalchemy import create_engine

# ---------------------------------------------------------------------------
# 1. KONFIGURASI — sesuaikan bagian ini
# ---------------------------------------------------------------------------

import os
from dotenv import load_dotenv

load_dotenv()
MYSQL_HOST = os.environ["MYSQL_HOST"]
MYSQL_PORT = os.environ["MYSQL_PORT"]
MYSQL_USER = os.environ["MYSQL_USER"]
MYSQL_PASSWORD = os.environ["MYSQL_PASSWORD"]
MYSQL_DB = os.environ["MYSQL_DB"]

MYSQL_URL = f"mysql+pymysql://{MYSQL_USER}:{MYSQL_PASSWORD}@{MYSQL_HOST}:{MYSQL_PORT}/{MYSQL_DB}"

# Daftar file DuckDB yang mau dimigrasi: (path_file, prefix_nama_tabel)
DUCKDB_SOURCES = [
    ("berita-dampak/data/ugm_news.duckdb", "berita_"),
    # tambahkan baris lain di sini kalau ada subproyek DuckDB lain, contoh:
    # ("matkul-sustainability/data/matkul.duckdb", "matkul_"),
]
CSV_SOURCES = []
# ---------------------------------------------------------------------------
# 2. PROSES MIGRASI — biasanya tidak perlu diubah
# ---------------------------------------------------------------------------

def migrasi_duckdb(path_file: str, prefix: str, mysql_engine):
    path_file = Path(path_file)
    if not path_file.exists():
        print(f"[SKIP] File tidak ditemukan: {path_file}")
        return

    print(f"\n=== Migrasi dari {path_file} ===")
    duck_con = duckdb.connect(str(path_file), read_only=True)
    tables = duck_con.execute("SHOW TABLES").fetchdf()["name"].tolist()
    print(f"Tabel ditemukan ({len(tables)}): {tables}")

    for t in tables:
        df = duck_con.execute(f"SELECT * FROM {t}").fetchdf()
        nama_tabel_baru = f"{prefix}{t}"
        df.to_sql(nama_tabel_baru, mysql_engine, if_exists="replace", index=False, chunksize=1000)
        print(f"  [OK] {t} -> {nama_tabel_baru}  ({len(df)} baris)")

    duck_con.close()


def migrasi_csv(path_file: str, nama_tabel: str, mysql_engine):
    path_file = Path(path_file)
    if not path_file.exists():
        print(f"[SKIP] File tidak ditemukan: {path_file}")
        return

    print(f"\n=== Migrasi dari {path_file} ===")
    df = pd.read_csv(path_file)
    df.to_sql(nama_tabel, mysql_engine, if_exists="replace", index=False, chunksize=1000)
    print(f"  [OK] {path_file.name} -> {nama_tabel}  ({len(df)} baris)")


def main():
    print("Menghubungkan ke MySQL...")
    mysql_engine = create_engine(MYSQL_URL)

    # tes koneksi dulu sebelum mulai migrasi apa pun
    with mysql_engine.connect() as conn:
        conn.exec_driver_sql("SELECT 1")
    print("Koneksi ke MySQL berhasil.\n")

    for path_file, prefix in DUCKDB_SOURCES:
        migrasi_duckdb(path_file, prefix, mysql_engine)

    for path_file, nama_tabel in CSV_SOURCES:
        migrasi_csv(path_file, nama_tabel, mysql_engine)

    print("\nSemua migrasi selesai.")


if __name__ == "__main__":
    main()