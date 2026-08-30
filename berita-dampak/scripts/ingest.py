"""Ingest berita UGM dari RSS ke MySQL.

Mengambil feed RSS terbaru (id + en) dan menyimpan judul, tautan,
tanggal terbit, dan deskripsi ke tabel `berita_berita` di MySQL.
"""

import html
import re
import sys
from pathlib import Path

import requests

sys.path.insert(0, str(Path(__file__).resolve().parent))
from db import ensure_url_primary_key, get_engine, t, upsert  # noqa: E402

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


COLUMNS = ["url", "judul", "tanggal", "deskripsi", "kategori", "sumber"]


def main() -> None:
    engine = get_engine()
    table = t("berita")
    with engine.begin() as conn:
        conn.exec_driver_sql(
            f"""
            CREATE TABLE IF NOT EXISTS `{table}` (
                url VARCHAR(500) PRIMARY KEY,
                judul TEXT,
                tanggal VARCHAR(40),
                deskripsi TEXT,
                kategori TEXT,
                sumber VARCHAR(20)
            )
            """
        )
    ensure_url_primary_key(engine, table)

    total = 0
    for feed in FEEDS:
        try:
            r = requests.get(feed, timeout=60, headers=HEADERS)
            r.raise_for_status()
            items = parse_feed(r.text)
        except Exception as e:  # noqa: BLE001
            print(f"GAGAL {feed}: {e}")
            continue
        saved = upsert(
            engine, table, COLUMNS,
            [(i["url"], i["judul"], i["tanggal"], i["deskripsi"], i["kategori"], i["sumber"]) for i in items],
            update_columns=["judul", "tanggal", "deskripsi", "kategori", "sumber"],
        )
        total += saved
        print(f"{feed}: {len(items)} item ({saved} tersimpan)")
    with engine.connect() as conn:
        n = conn.exec_driver_sql(f"SELECT COUNT(*) FROM `{table}`").scalar()
    print(f"SELESAI. Total baris berita (dari RSS): {n}")


if __name__ == "__main__":
    main()
