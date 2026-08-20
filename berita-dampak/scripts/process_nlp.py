"""Tagging topik dampak pada berita UGM (substring match pada judul + deskripsi).

Menggunakan kamus keywords.py. Satu berita bisa masuk lebih dari satu topik.
Hasil: tabel `berita_topik` (url, topik) dan tabel `ringkasan_topik_tahun`.
"""

import re
import sys
from pathlib import Path

import duckdb

sys.path.insert(0, str(Path(__file__).resolve().parent))
from keywords import KEYWORDS  # noqa: E402

DB_PATH = Path(__file__).resolve().parents[1] / "data" / "ugm_news.duckdb"


def tag(text: str) -> list[str]:
    t = text.lower()
    hits = []
    for topik, kws in KEYWORDS.items():
        for kw in kws:
            if kw in t:
                hits.append(topik)
                break
    return hits


def main() -> None:
    con = duckdb.connect(str(DB_PATH))
    rows = con.execute("SELECT url, judul, deskripsi FROM berita").fetchall()
    tagged = [(url, topik) for url, judul, deskripsi in rows for topik in tag(f"{judul} {deskripsi}")]

    con.execute("CREATE OR REPLACE TABLE berita_topik (url VARCHAR, topik VARCHAR)")
    con.executemany("INSERT INTO berita_topik VALUES (?, ?)", tagged)

    con.execute(
        """
        CREATE OR REPLACE TABLE ringkasan_topik_tahun AS
        SELECT b.topik,
               strftime(CAST(bt.tanggal AS DATE), '%Y') AS tahun,
               COUNT(*) AS jumlah
        FROM berita_topik b
        JOIN berita bt ON bt.url = b.url
        WHERE bt.tanggal IS NOT NULL
        GROUP BY b.topik, tahun
        ORDER BY b.topik, tahun
        """
    )
    print("Per topik:")
    for topik, n in con.execute(
        "SELECT topik, COUNT(*) FROM berita_topik GROUP BY topik ORDER BY COUNT(*) DESC"
    ).fetchall():
        print(f"  {topik}: {n} berita")
    print(f"Total pasangan topik: {len(tagged)}")
    con.close()


if __name__ == "__main__":
    main()
