"""Tagging berita dampak ke Topik Resmi Kepmen 361/M/KEP/2025 + Klaster SDGs.

Input : data/ugm_news.duckdb — tabel berita_topik (url, topik).
Output: tabel baru:
  - berita_kepmen : url, topik, dampak, topik_kepmen  (per url+topik)
  - berita_sdg    : url, sdg                          (dedup per url)
  - ringkasan_sdg : sdg, nama_sdg, jumlah_berita

Mapping dari scripts/kepmen_sdg.py (bersumber UGM Analytics.xlsx, sheet
"Konten UGM Berdampak" + "#Ref"). SDG dideduplikasi per url karena dua topik
bisa memetakan ke SDG yang sama.

Jalankan (dari folder berita-dampak):
  ../venv/Scripts/python.exe scripts/tag_kepmen_berita.py
"""

import sys
from pathlib import Path

import duckdb
import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parent))
from kepmen_sdg import SDG_NAMA, TOPIK_KEPMEN  # noqa: E402

DB = Path(__file__).resolve().parents[1] / "data" / "ugm_news.duckdb"


def main() -> None:
    con = duckdb.connect(str(DB))
    topik = con.execute("SELECT url, topik FROM berita_topik").fetchdf()
    if len(topik) == 0:
        print("berita_topik kosong — tidak ada yang ditag.")
        return

    # (url, topik) → (url, topik, dampak, topik_kepmen)
    rows = []
    for _, r in topik.iterrows():
        meta = TOPIK_KEPMEN.get(r["topik"])
        if not meta:
            continue
        rows.append(
            {
                "url": r["url"],
                "topik": r["topik"],
                "dampak": meta["dampak"],
                "topik_kepmen": meta["topik_kepmen"],
            }
        )
    df_kepmen = pd.DataFrame(rows)

    # (url, sdg) — dedup karena multi-topik bisa overlap SDG
    sdg_rows = []
    for _, r in df_kepmen.iterrows():
        for sdg in TOPIK_KEPMEN[r["topik"]]["sdg"]:
            sdg_rows.append({"url": r["url"], "sdg": sdg})
    df_sdg = pd.DataFrame(sdg_rows).drop_duplicates(subset=["url", "sdg"])

    con.execute("DROP TABLE IF EXISTS berita_kepmen")
    con.execute("DROP TABLE IF EXISTS berita_sdg")
    con.execute("DROP TABLE IF EXISTS ringkasan_sdg")
    con.execute("CREATE TABLE berita_kepmen (url VARCHAR, topik VARCHAR, "
                "dampak VARCHAR, topik_kepmen VARCHAR)")
    con.execute("CREATE TABLE berita_sdg (url VARCHAR, sdg INTEGER)")
    con.execute("CREATE TABLE ringkasan_sdg (sdg INTEGER, nama_sdg VARCHAR, "
                "jumlah_berita BIGINT)")

    con.executemany(
        "INSERT INTO berita_kepmen VALUES (?, ?, ?, ?)",
        df_kepmen.itertuples(index=False, name=None),
    )
    con.executemany(
        "INSERT INTO berita_sdg VALUES (?, ?)",
        df_sdg.itertuples(index=False, name=None),
    )
    ring = (
        df_sdg.groupby("sdg")["url"]
        .nunique()
        .reset_index(name="jumlah_berita")
        .sort_values("sdg")
    )
    con.executemany(
        "INSERT INTO ringkasan_sdg VALUES (?, ?, ?)",
        [
            (int(r.sdg), SDG_NAMA[int(r.sdg)], int(r.jumlah_berita))
            for r in ring.itertuples()
        ],
    )

    n_berita_sdg = df_sdg["url"].nunique()
    n_berita_kepmen = df_kepmen["url"].nunique()
    con.close()

    print(f"Baris url–topik Kepmen: {len(df_kepmen)}")
    print(f"Baris url–SDG (dedup): {len(df_sdg)}")
    print(f"Berita unik dengan SDG: {n_berita_sdg}")
    print(f"Berita unik dengan topik Kepmen: {n_berita_kepmen}")
    print("Tabel baru: berita_kepmen, berita_sdg, ringkasan_sdg")


if __name__ == "__main__":
    main()
