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


COLUMNS = ["url", "judul", "tanggal", "deskripsi", "kategori", "sumber", "isi", "kredit"]


def main() -> None:
    engine = get_engine()
    table = t("berita")

    # isi/kredit (scripts/fetch_backlog.py) dibaca & ditulis balik APA ADANYA
    # (bukan lewat clean_text) -- kalau kolomnya belum ada (belum pernah
    # jalanin fetch_backlog.py), SELECT * otomatis tidak menyertakannya dan
    # kita treat sebagai kosong; JANGAN ganti ke SELECT eksplisit 6 kolom
    # lama, itu pernah jadi bug nyata: DELETE+INSERT ulang tabel ini cuma
    # bawa 6 kolom lama akan diam-diam menghapus isi/kredit semua baris di
    # setiap update mingguan.
    def _read_all():
        with engine.connect() as conn:
            cols = {
                r[0] for r in conn.exec_driver_sql(f"SHOW COLUMNS FROM `{table}`").fetchall()
            }
            has_isi = "isi" in cols and "kredit" in cols
            select_cols = (
                "url, judul, tanggal, deskripsi, kategori, sumber, isi, kredit"
                if has_isi else
                "url, judul, tanggal, deskripsi, kategori, sumber"
            )
            rows_ = conn.exec_driver_sql(f"SELECT {select_cols} FROM `{table}`").fetchall()
            return rows_, has_isi

    ok, result = with_retry(_read_all, label="baca tabel berita")
    if not ok:
        print("GAGAL membaca tabel berita dari MySQL setelah 3 percobaan -- batal.")
        return
    rows, has_isi = result
    print(f"Sebelum normalisasi: {len(rows)} baris "
          f"(kolom isi/kredit: {'ada' if has_isi else 'belum ada'})")

    cleaned = []
    seen = set()
    for row in rows:
        if has_isi:
            url, judul, tanggal, deskripsi, kategori, sumber, isi, kredit = row
        else:
            url, judul, tanggal, deskripsi, kategori, sumber = row
            isi, kredit = None, None
        u = url.split("?")[0].strip().rstrip("/")
        if not u or u in seen:
            continue  # duplikat URL (bentuk mentah vs bersih) — baris kedua dibuang
        seen.add(u)
        j = clean_text(judul)
        d = clean_text(deskripsi)
        k = clean_text(kategori)
        if not j:
            continue  # baris tanpa judul tidak berguna
        cleaned.append((u, j, parse_date(tanggal), d, k, sumber, isi, kredit))

    # Kolom aktual dipakai sesuai has_isi (kalau isi/kredit belum ada di
    # tabel -- mis. sebelum fetch_backlog.py pernah jalan sekalipun -- jangan
    # sisipkan kolom yang tidak ada, INSERT akan gagal).
    insert_cols = COLUMNS if has_isi else COLUMNS[:-2]

    # DELETE + INSERT dalam SATU transaksi: kalau proses berhenti di tengah
    # (atau gagal), rollback otomatis mengembalikan tabel ke kondisi sebelum
    # normalisasi -- bukan tabel kosong. `cleaned` dihitung di memori (murah,
    # tanpa network), jadi aman diulang total kalau transaksi ini gagal.
    def _replace_all():
        with engine.begin() as conn:
            conn.execute(text(f"DELETE FROM `{table}`"))
            if cleaned:
                cols_sql = ", ".join(f"`{c}`" for c in insert_cols)
                placeholders = ", ".join(f":{c}" for c in insert_cols)
                data = [dict(zip(insert_cols, row[: len(insert_cols)])) for row in cleaned]
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
