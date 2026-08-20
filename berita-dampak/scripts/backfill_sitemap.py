"""Backfill berita UGM dari sitemap ke DuckDB.

Mengambil seluruh post-sitemapN.xml dari ugm.ac.id dan menyimpan
URL + lastmod ke tabel `sitemap` di data/ugm_news.duckdb.
"""

import re
import time
from pathlib import Path

import duckdb
import requests

DB_PATH = Path(__file__).resolve().parents[1] / "data" / "ugm_news.duckdb"
SITEMAP_INDEX = "https://ugm.ac.id/wp-sitemap.xml"
HEADERS = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 Chrome/126.0 Safari/537.36"}


def get(url: str, retries: int = 4) -> str:
    last_err: Exception | None = None
    for attempt in range(retries):
        try:
            r = requests.get(url, timeout=60, headers=HEADERS)
            r.raise_for_status()
            return r.text
        except Exception as e:  # noqa: BLE001
            last_err = e
            print(f"    (percobaan {attempt + 1} gagal untuk {url}: {e})")
            time.sleep(3 * (attempt + 1))
    raise last_err  # type: ignore[misc]


def sitemap_urls() -> list[str]:
    """Daftar post-sitemapN.xml dari sitemap index."""
    idx = get(SITEMAP_INDEX)
    locs = re.findall(r"<loc>(https://ugm\.ac\.id/post-sitemap\d+\.xml)</loc>", idx)
    return sorted(set(locs))


def parse_entries(xml: str) -> list[tuple[str, str]]:
    """Ekstrak (url, lastmod) dari satu sitemap."""
    out = []
    for m in re.finditer(r"<url>\s*<loc>(.*?)</loc>\s*<lastmod>(.*?)</lastmod>", xml, re.S):
        out.append((m.group(1).strip(), m.group(2).strip()))
    return out


def main() -> None:
    con = duckdb.connect(str(DB_PATH))
    con.execute(
        """
        CREATE TABLE IF NOT EXISTS sitemap (
            url VARCHAR PRIMARY KEY,
            lastmod VARCHAR,
            diambil TIMESTAMP DEFAULT current_timestamp
        )
        """
    )
    total_new = 0
    for i, sm in enumerate(sitemap_urls(), 1):
        try:
            entries = parse_entries(get(sm))
        except Exception as e:  # noqa: BLE001
            print(f"[{i}/{len(sitemap_urls())}] GAGAL {sm}: {e}")
            continue
        con.executemany("INSERT OR IGNORE INTO sitemap (url, lastmod) VALUES (?, ?)", entries)
        total_new += len(entries)
        print(f"[{i}/{len(sitemap_urls())}] {sm}: {len(entries)} URL (total {total_new})")
    n = con.execute("SELECT COUNT(*) FROM sitemap").fetchone()[0]
    print(f"SELESAI. Total baris sitemap: {n}")
    con.close()


if __name__ == "__main__":
    main()
