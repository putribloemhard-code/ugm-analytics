"""Backfill deskripsi berita sitemap yang kosong (fallback og:description).

Sekali pakai (2026-08-20): fetch_detail.py sebelumnya hanya membaca
<meta name="description">; banyak halaman ugm.ac.id hanya punya
og:description → 1.968 berita sitemap deskripsinya kosong. Script ini
fetch ulang URL-URL itu dengan fetch_detail yang sudah diperbaiki dan
UPDATE deskripsi. Idempoten: hanya URL dengan deskripsi kosong.

Jalankan (dari folder berita-dampak):
  ../venv/Scripts/python.exe scripts/backfill_deskripsi.py
"""

import sys
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path

import duckdb

sys.path.insert(0, str(Path(__file__).resolve().parent))
from fetch_detail import fetch_detail  # noqa: E402

DB = Path(__file__).resolve().parents[1] / "data" / "ugm_news.duckdb"


def main() -> None:
    con = duckdb.connect(str(DB))
    rows = con.execute(
        "SELECT url FROM berita WHERE sumber='sitemap' "
        "AND (deskripsi IS NULL OR deskripsi='')"
    ).fetchall()
    print(f"Berita sitemap tanpa deskripsi: {len(rows)}")
    if not rows:
        con.close()
        return

    total = 0
    with ThreadPoolExecutor(max_workers=8) as pool:
        futures = {pool.submit(fetch_detail, url): url for (url,) in rows}
        for i, fut in enumerate(as_completed(futures), 1):
            url = futures[fut]
            detail = fut.result()
            if detail and detail["deskripsi"]:
                con.execute(
                    "UPDATE berita SET deskripsi=? WHERE url=?",
                    (detail["deskripsi"], url),
                )
                total += 1
            if i % 200 == 0:
                print(f"  ... {i}/{len(rows)} ({total} terisi)", flush=True)
            time.sleep(0.05)

    sisa = con.execute(
        "SELECT COUNT(*) FROM berita WHERE sumber='sitemap' "
        "AND (deskripsi IS NULL OR deskripsi='')"
    ).fetchone()[0]
    print(f"SELESAI. {total} deskripsi terisi. Masih kosong: {sisa}")
    con.close()


if __name__ == "__main__":
    main()
