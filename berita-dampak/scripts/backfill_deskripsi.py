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

from sqlalchemy import text

sys.path.insert(0, str(Path(__file__).resolve().parent))
from db import get_engine, t, with_retry  # noqa: E402
from fetch_detail import fetch_detail  # noqa: E402


def main() -> None:
    engine = get_engine()
    table = t("berita")

    def _read_kosong():
        with engine.connect() as conn:
            return conn.exec_driver_sql(
                f"SELECT url FROM `{table}` WHERE sumber='sitemap' "
                "AND (deskripsi IS NULL OR deskripsi='')"
            ).fetchall()

    ok, rows = with_retry(_read_kosong, label="baca berita tanpa deskripsi")
    if not ok:
        print("GAGAL membaca daftar berita dari MySQL setelah 3 percobaan -- batal.")
        return
    print(f"Berita sitemap tanpa deskripsi: {len(rows)}")
    if not rows:
        return

    total = 0
    gagal = 0
    with ThreadPoolExecutor(max_workers=8) as pool:
        futures = {pool.submit(fetch_detail, url): url for (url,) in rows}
        for i, fut in enumerate(as_completed(futures), 1):
            url = futures[fut]
            detail = fut.result()
            if detail and detail["deskripsi"]:
                def _update():
                    with engine.begin() as conn:
                        conn.execute(
                            text(f"UPDATE `{table}` SET deskripsi=:d WHERE url=:u"),
                            {"d": detail["deskripsi"], "u": url},
                        )

                ok, _ = with_retry(_update, label=f"UPDATE deskripsi {url}")
                if ok:
                    total += 1
                else:
                    # Satu URL gagal setelah 3x retry -- dilog (oleh with_retry)
                    # dan dilewati; TIDAK menghentikan sisa batch.
                    gagal += 1
            if i % 200 == 0:
                print(f"  ... {i}/{len(rows)} ({total} terisi, {gagal} gagal)", flush=True)
            time.sleep(0.05)

    def _count_sisa():
        with engine.connect() as conn:
            return conn.exec_driver_sql(
                f"SELECT COUNT(*) FROM `{table}` WHERE sumber='sitemap' "
                "AND (deskripsi IS NULL OR deskripsi='')"
            ).scalar()

    ok, sisa = with_retry(_count_sisa, label="hitung sisa berita tanpa deskripsi")
    print(f"SELESAI. {total} deskripsi terisi ({gagal} gagal setelah retry). "
          f"Masih kosong: {sisa if ok else '?'}")


if __name__ == "__main__":
    main()
