from __future__ import annotations

import os
from pathlib import Path

import duckdb
from sqlalchemy import URL, create_engine, text

SOURCE = Path(os.environ.get("DUCKDB_SOURCE", "/bootstrap/ugm_news.duckdb"))
TABLES = {
    "sitemap": "berita_sitemap",
    "berita": "berita_berita",
    "berita_kepmen_all": "berita_berita_kepmen_all",
    "berita_sdg_all": "berita_berita_sdg_all",
    "sitemap_sdg": "berita_sitemap_sdg",
    "berita_topik": "berita_berita_topik",
    "ringkasan_pilar": "berita_ringkasan_pilar",
    "ringkasan_pilar_tahun": "berita_ringkasan_pilar_tahun",
    "ringkasan_topik_all": "berita_ringkasan_topik_all",
    "ringkasan_topik_tahun": "berita_ringkasan_topik_tahun",
    "ringkasan_sdg_all": "berita_ringkasan_sdg_all",
    "ringkasan_sdg_sitemap": "berita_ringkasan_sdg_sitemap",
    "ringkasan_sdg_sitemap_tahun": "berita_ringkasan_sdg_sitemap_tahun",
}


def engine_url() -> URL:
    return URL.create(
        "postgresql+psycopg",
        username=os.environ["POSTGRES_USER"],
        password=os.environ["POSTGRES_PASSWORD"],
        host=os.environ.get("POSTGRES_HOST", "postgres"),
        port=int(os.environ.get("POSTGRES_PORT", "5432")),
        database=os.environ["POSTGRES_DB"],
    )


def main() -> None:
    if not SOURCE.is_file():
        raise SystemExit(f"DuckDB source missing: {SOURCE}")
    source = duckdb.connect(str(SOURCE), read_only=True)
    engine = create_engine(engine_url())
    with engine.begin() as conn:
        exists = conn.execute(text("SELECT to_regclass('public.berita_berita')")).scalar()
        if exists:
            raise SystemExit("Bootstrap refused: berita_berita already exists")
    for source_table, target_table in TABLES.items():
        frame = source.execute(f'SELECT * FROM "{source_table}"').fetchdf()
        frame.to_sql(target_table, engine, if_exists="fail", index=False, method="multi", chunksize=1000)
        print(f"imported {source_table} -> {target_table}: {len(frame)} rows")
    with engine.begin() as conn:
        conn.execute(text("CREATE TABLE berita_unit_kerja (url TEXT NOT NULL, unit_kerja TEXT NOT NULL)"))
        conn.execute(text("CREATE INDEX berita_berita_tanggal_idx ON berita_berita (tanggal)"))
        conn.execute(text("CREATE INDEX berita_kepmen_url_idx ON berita_berita_kepmen_all (url)"))
        conn.execute(text("CREATE INDEX berita_sitemap_sdg_url_idx ON berita_sitemap_sdg (url)"))
        conn.execute(text("CREATE INDEX berita_unit_url_idx ON berita_unit_kerja (url)"))
    print("bootstrap complete")


if __name__ == "__main__":
    main()
