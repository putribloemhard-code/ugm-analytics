from __future__ import annotations

import os
from pathlib import Path

import pandas as pd
from sqlalchemy import URL, create_engine, inspect, text

BATCH_SIZE = 1_000


def url(driver: str, prefix: str) -> URL:
    return URL.create(
        driver,
        username=os.environ[f"{prefix}_USER"],
        password=os.environ[f"{prefix}_PASSWORD"],
        host=os.environ[f"{prefix}_HOST"],
        port=int(os.environ[f"{prefix}_PORT"]),
        database=os.environ[f"{prefix}_DB"],
    )


def main() -> None:
    source = create_engine(url("mysql+pymysql", "SOURCE_MYSQL"), pool_pre_ping=True)
    target = create_engine(url("postgresql+psycopg", "POSTGRES"), pool_pre_ping=True)
    source_tables = inspect(source).get_table_names()
    if not source_tables:
        raise SystemExit("Source MySQL has no tables")
    with target.begin() as conn:
        if conn.execute(text("SELECT to_regclass('public.berita_berita')")).scalar():
            raise SystemExit("Target PostgreSQL already contains berita_berita; refusing overwrite")
    for table in source_tables:
        total = 0
        for frame in pd.read_sql_table(table, source, chunksize=BATCH_SIZE):
            frame.to_sql(table, target, if_exists="append" if total else "fail", index=False, method="multi", chunksize=BATCH_SIZE)
            total += len(frame)
        if total == 0:
            columns = [column["name"] for column in inspect(source).get_columns(table)]
            pd.DataFrame(columns=columns).to_sql(table, target, if_exists="fail", index=False)
        print(f"copied {table}: {total} rows")
    with target.begin() as conn:
        conn.execute(text("CREATE INDEX berita_berita_tanggal_idx ON berita_berita (tanggal)"))
        conn.execute(text("CREATE INDEX berita_kepmen_url_idx ON berita_berita_kepmen_all (url)"))
        conn.execute(text("CREATE INDEX berita_sitemap_sdg_url_idx ON berita_sitemap_sdg (url)"))
        conn.execute(text("CREATE INDEX berita_unit_url_idx ON berita_unit_kerja (url)"))
    print("migration complete")


if __name__ == "__main__":
    main()
