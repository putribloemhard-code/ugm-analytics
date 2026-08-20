"""Normalisasi hasil ekstraksi berita dampak UGM.

- Membersihkan judul/deskripsi (whitespace, HTML sisa, duplikat spasi).
- Konversi tanggal RSS (RFC 822) dan ISO 8601 ke format YYYY-MM-DD.
- Menghapus duplikat URL (case/query string).
- Menandai baris tanpa judul sebagai tidak valid (dihapus).
"""

import re
from datetime import datetime
from email.utils import parsedate_to_datetime
from pathlib import Path

import duckdb

DB_PATH = Path(__file__).resolve().parents[1] / "data" / "ugm_news.duckdb"


def clean_text(s: str | None) -> str:
    if not s:
        return ""
    s = re.sub(r"<[^>]+>", " ", s)
    s = s.replace("&nbsp;", " ").replace("&amp;", "&").replace("&quot;", '"')
    return re.sub(r"\s+", " ", s).strip()


def parse_date(s: str | None) -> str | None:
    if not s:
        return None
    s = s.strip()
    if re.match(r"\d{4}-\d{2}-\d{2}", s):
        return s[:10]
    try:
        return parsedate_to_datetime(s).strftime("%Y-%m-%d")
    except Exception:  # noqa: BLE001
        return None


def main() -> None:
    con = duckdb.connect(str(DB_PATH))
    rows = con.execute(
        "SELECT url, judul, tanggal, deskripsi, kategori, sumber FROM berita"
    ).fetchall()
    print(f"Sebelum normalisasi: {len(rows)} baris")

    cleaned = []
    seen = set()
    for url, judul, tanggal, deskripsi, kategori, sumber in rows:
        u = url.split("?")[0].strip().rstrip("/")
        if not u or u in seen:
            continue  # duplikat URL (bentuk mentah vs bersih) — baris kedua dibuang
        seen.add(u)
        j = clean_text(judul)
        d = clean_text(deskripsi)
        k = clean_text(kategori)
        if not j:
            continue  # baris tanpa judul tidak berguna
        cleaned.append((u, j, parse_date(tanggal), d, k, sumber))

    con.execute("DELETE FROM berita")
    con.executemany(
        "INSERT INTO berita (url, judul, tanggal, deskripsi, kategori, sumber) VALUES (?,?,?,?,?,?)",
        cleaned,
    )
    n = con.execute("SELECT COUNT(*) FROM berita").fetchone()[0]
    n_date = con.execute("SELECT COUNT(*) FROM berita WHERE tanggal IS NOT NULL").fetchone()[0]
    print(f"Sesudah normalisasi: {n} baris (dengan tanggal: {n_date})")
    con.close()


if __name__ == "__main__":
    main()
