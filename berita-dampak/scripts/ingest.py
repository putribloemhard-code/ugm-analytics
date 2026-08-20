"""Ingest berita UGM dari RSS ke DuckDB.

Mengambil feed RSS terbaru (id + en) dan menyimpan judul, tautan,
tanggal terbit, dan deskripsi ke tabel `berita` di data/ugm_news.duckdb.
"""

import html
import re
from pathlib import Path

import duckdb
import requests

DB_PATH = Path(__file__).resolve().parents[1] / "data" / "ugm_news.duckdb"
FEEDS = [
    "https://ugm.ac.id/id/feed/",
    "https://ugm.ac.id/en/feed/",
]
HEADERS = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 Chrome/126.0 Safari/537.36"}


def parse_feed(xml: str) -> list[dict]:
    out = []
    for m in re.finditer(r"<item>(.*?)</item>", xml, re.S):
        body = m.group(1)
        title = re.search(r"<title>(.*?)</title>", body, re.S)
        link = re.search(r"<link>(.*?)</link>", body, re.S)
        pub = re.search(r"<pubDate>(.*?)</pubDate>", body, re.S)
        desc = re.search(r"<description>(?:<!\[CDATA\[)?(.*?)(?:\]\]>)?</description>", body, re.S)
        cats = re.findall(r"<category>(?:<!\[CDATA\[)?(.*?)(?:\]\]>)?</category>", body, re.S)
        if not (title and link):
            continue
        d = html.unescape(desc.group(1)) if desc else ""
        d = re.sub(r"<[^>]+>", " ", d)
        out.append(
            {
                "judul": html.unescape(title.group(1)).strip(),
                "url": link.group(1).strip(),
                "tanggal": pub.group(1).strip() if pub else None,
                "deskripsi": re.sub(r"\s+", " ", d).strip(),
                "kategori": ", ".join(html.unescape(c).strip() for c in cats),
                "sumber": "rss",
            }
        )
    return out


def main() -> None:
    con = duckdb.connect(str(DB_PATH))
    con.execute(
        """
        CREATE TABLE IF NOT EXISTS berita (
            url VARCHAR PRIMARY KEY,
            judul VARCHAR,
            tanggal VARCHAR,
            deskripsi VARCHAR,
            kategori VARCHAR,
            sumber VARCHAR
        )
        """
    )
    total = 0
    for feed in FEEDS:
        try:
            r = requests.get(feed, timeout=60, headers=HEADERS)
            r.raise_for_status()
            items = parse_feed(r.text)
        except Exception as e:  # noqa: BLE001
            print(f"GAGAL {feed}: {e}")
            continue
        con.executemany(
            "INSERT OR IGNORE INTO berita (url, judul, tanggal, deskripsi, kategori, sumber) VALUES (?,?,?,?,?,?)",
            [(i["url"], i["judul"], i["tanggal"], i["deskripsi"], i["kategori"], i["sumber"]) for i in items],
        )
        total += len(items)
        print(f"{feed}: {len(items)} item")
    n = con.execute("SELECT COUNT(*) FROM berita").fetchone()[0]
    print(f"SELESAI. Total baris berita (dari RSS): {n}")
    con.close()


if __name__ == "__main__":
    main()
