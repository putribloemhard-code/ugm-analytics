"""Tagging eksplorasi berita ke SEMUA tema resmi Kepmen 361/M/KEP/2025.

Melengkapi tag_kepmen_berita.py yang hanya menag 4 topik inti. Di sini semua
berita di tabel `berita` dicocokkan (keyword substring, case-insensitive,
judul + deskripsi) ke 9 tema tambahan: pendidikan inklusif, penelitian &
inovasi, pengabdian masyarakat, instansi publik, pengajaran & pembelajaran,
belanja UMKM, energi, limbah, transportasi.

Output tabel baru:
  - berita_kepmen_lengkap : url, topik, dampak, topik_kepmen
  - ringkasan_kepmen_lengkap : topik, dampak, topik_kepmen, jumlah_berita

Keyword di scripts/kepmen_sdg.py (TEMA_KEPMEN_LENGKAP). Berita bisa match
>1 tema (multi-tag by design). Idempoten (DROP + recreate).

Jalankan (dari folder berita-dampak):
  ../venv/Scripts/python.exe scripts/tag_kepmen_lengkap.py
"""

import re
import sys
from pathlib import Path

import duckdb
import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parent))
from kepmen_sdg import TEMA_KEPMEN_LENGKAP  # noqa: E402

DB = Path(__file__).resolve().parents[1] / "data" / "ugm_news.duckdb"


def main() -> None:
    con = duckdb.connect(str(DB))
    berita = con.execute("SELECT url, judul, deskripsi FROM berita").fetchdf()
    teks = (berita["judul"].fillna("") + " " + berita["deskripsi"].fillna("")).str.lower()

    rows = []
    for _, r in berita.iterrows():
        t = f"{r['judul'] or ''} {r['deskripsi'] or ''}".lower()
        for topik_id, meta in TEMA_KEPMEN_LENGKAP.items():
            if any(re.search(re.escape(kw), t) for kw in meta["keywords"]):
                rows.append(
                    {
                        "url": r["url"],
                        "topik": topik_id,
                        "dampak": meta["dampak"],
                        "topik_kepmen": meta["topik_kepmen"],
                    }
                )
    df = pd.DataFrame(rows)

    con.execute("DROP TABLE IF EXISTS berita_kepmen_lengkap")
    con.execute("DROP TABLE IF EXISTS ringkasan_kepmen_lengkap")
    con.execute("CREATE TABLE berita_kepmen_lengkap (url VARCHAR, topik VARCHAR, "
                "dampak VARCHAR, topik_kepmen VARCHAR)")
    con.execute("CREATE TABLE ringkasan_kepmen_lengkap (topik VARCHAR, "
                "dampak VARCHAR, topik_kepmen VARCHAR, jumlah_berita BIGINT)")
    con.executemany(
        "INSERT INTO berita_kepmen_lengkap VALUES (?, ?, ?, ?)",
        df.itertuples(index=False, name=None),
    )
    ring = (
        df.groupby(["topik", "dampak", "topik_kepmen"])["url"]
        .nunique()
        .reset_index(name="jumlah_berita")
        .sort_values("jumlah_berita", ascending=False)
    )
    con.executemany(
        "INSERT INTO ringkasan_kepmen_lengkap VALUES (?, ?, ?, ?)",
        ring.itertuples(index=False, name=None),
    )
    n_berita = df["url"].nunique()
    con.close()
    print(f"Baris url–tema: {len(df)}")
    print(f"Berita unik yang match ≥1 tema tambahan: {n_berita}")
    print("Tabel baru: berita_kepmen_lengkap, ringkasan_kepmen_lengkap")


if __name__ == "__main__":
    main()
