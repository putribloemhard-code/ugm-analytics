"""Backfill berita UGM dari sitemap ke MySQL.

Mengambil seluruh post-sitemapN.xml dari ugm.ac.id dan menyimpan
URL + lastmod ke tabel `berita_sitemap` di MySQL.
"""

import re
import sys
import time
from pathlib import Path

import requests

sys.path.insert(0, str(Path(__file__).resolve().parent))
from db import ensure_url_primary_key, get_engine, t, upsert  # noqa: E402

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
    engine = get_engine()
    table = t("sitemap")
    with engine.begin() as conn:
        conn.exec_driver_sql(
            f"""
            CREATE TABLE IF NOT EXISTS `{table}` (
                url VARCHAR(500) PRIMARY KEY,
                lastmod VARCHAR(40),
                diambil TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
            """
        )
    ensure_url_primary_key(engine, table)

    total_new = 0
    sms = sitemap_urls()
    for i, sm in enumerate(sms, 1):
        try:
            entries = parse_entries(get(sm))
        except Exception as e:  # noqa: BLE001
            print(f"[{i}/{len(sms)}] GAGAL {sm}: {e}")
            continue
        saved = upsert(engine, table, ["url", "lastmod"], entries, update_columns=["lastmod"])
        total_new += saved
        print(f"[{i}/{len(sms)}] {sm}: {len(entries)} URL ({saved} tersimpan, total {total_new})")
    with engine.connect() as conn:
        n = conn.exec_driver_sql(f"SELECT COUNT(*) FROM `{table}`").scalar()
    print(f"SELESAI. Total baris sitemap: {n}")


if __name__ == "__main__":
    main()
