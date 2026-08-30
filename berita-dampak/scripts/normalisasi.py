"""Normalisasi hasil ekstraksi berita dampak UGM.

- Membersihkan judul/deskripsi (whitespace, HTML sisa, duplikat spasi).
- Konversi tanggal RSS (RFC 822) dan ISO 8601 ke format YYYY-MM-DD.
- Menghapus duplikat URL (case/query string).
- Menandai baris tanpa judul sebagai tidak valid (dihapus).
"""

import re
import sys
from email.utils import parsedate_to_datetime
from pathlib import Path

from sqlalchemy import text

sys.path.insert(0, str(Path(__file__).resolve().parent))
from db import get_engine, t, with_retry  # noqa: E402


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


COLUMNS = ["url", "judul", "tanggal", "deskripsi", "kategori", "sumber"]


def main() -> None:
    engine = get_engine()
    table = t("berita")

    def _read_all():
        with engine.connect() as conn:
            return conn.exec_driver_sql(
                f"SELECT url, judul, tanggal, deskripsi, kategori, sumber FROM `{table}`"
            ).fetchall()

    ok, rows = with_retry(_read_all, label="baca tabel berita")
    if not ok:
        print("GAGAL membaca tabel berita dari MySQL setelah 3 percobaan -- batal.")
        return
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

    # DELETE + INSERT dalam SATU transaksi: kalau proses berhenti di tengah
    # (atau gagal), rollback otomatis mengembalikan tabel ke kondisi sebelum
    # normalisasi -- bukan tabel kosong. `cleaned` dihitung di memori (murah,
    # tanpa network), jadi aman diulang total kalau transaksi ini gagal.
    def _replace_all():
        with engine.begin() as conn:
            conn.execute(text(f"DELETE FROM `{table}`"))
            if cleaned:
                cols_sql = ", ".join(f"`{c}`" for c in COLUMNS)
                placeholders = ", ".join(f":{c}" for c in COLUMNS)
                data = [dict(zip(COLUMNS, row)) for row in cleaned]
                conn.execute(
                    text(f"INSERT INTO `{table}` ({cols_sql}) VALUES ({placeholders})"),
                    data,
                )

    ok, _ = with_retry(_replace_all, label="tulis ulang tabel berita (normalisasi)")
    if not ok:
        print("GAGAL menyimpan hasil normalisasi ke MySQL setelah 3 percobaan -- "
              "tabel berita TIDAK berubah (transaksi di-rollback).")
        return

    def _count():
        with engine.connect() as conn:
            n_ = conn.exec_driver_sql(f"SELECT COUNT(*) FROM `{table}`").scalar()
            n_date_ = conn.exec_driver_sql(
                f"SELECT COUNT(*) FROM `{table}` WHERE tanggal IS NOT NULL"
            ).scalar()
        return n_, n_date_

    ok, result = with_retry(_count, label="hitung ulang tabel berita")
    if ok:
        n, n_date = result
        print(f"Sesudah normalisasi: {n} baris (dengan tanggal: {n_date})")


if __name__ == "__main__":
    main()
