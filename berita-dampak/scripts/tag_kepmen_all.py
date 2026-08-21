"""Tagging berita ke SEMUA tema resmi Kepmen 361/M/KEP/2025 (14 tema: 4 inti + 10 lengkap).

Menggantikan tag_kepmen_berita.py (4 topik inti) dan tag_kepmen_lengkap.py
(9 topik tambahan) menjadi satu pipeline: semua berita di tabel `berita`
dicocokkan (keyword substring, case-insensitive, judul + deskripsi) ke 14 tema,
tiap tema membawa pilar (Sosial/Ekonomi/Lingkungan) dan klaster SDGs dari
UGM Analytics.xlsx (sheet Konten + #Ref).

Output tabel baru (idempoten, DROP + recreate):
  - berita_kepmen_all : url, topik, dampak, topik_kepmen, sdg
                        (sdg = list SDG topik itu, digabung '|' — semua berita
                        dalam satu topik membawa SDG yang sama; lihat pitfall
                        konseptual di references/kepmen-sdg-berita.md)
  - berita_sdg_all    : url, sdg (satu baris per pasangan url–sdg, dedup —
                        berita multi-topik bisa memetakan ke SDG sama)
  - ringkasan_topik_all   : topik, dampak, topik_kepmen, sdg, jumlah_berita
                        (selalu 14 baris — semua tema resmi, 0 utk yang tak ada match)
  - ringkasan_pilar       : dampak, jumlah_berita (berita unik)
  - ringkasan_pilar_tahun : dampak, tahun, jumlah_berita
  - ringkasan_sdg_all     : sdg, nama_sdg, jumlah_berita

Keyword: TOPIK_KEPMEN (4 inti, di scripts/keywords.py) + TEMA_KEPMEN_LENGKAP
(10 tambahan, di scripts/kepmen_sdg.py). Berita bisa match >1 tema (multi-tag
by design).

Jalankan (dari folder berita-dampak):
  ../venv/Scripts/python.exe scripts/tag_kepmen_all.py
"""

import re
import sys
from pathlib import Path

import duckdb
import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parent))
from kepmen_sdg import SDG_NAMA, TEMA_KEPMEN_LENGKAP, TOPIK_KEPMEN  # noqa: E402
from keywords import KEYWORDS  # noqa: E402

DB = Path(__file__).resolve().parents[1] / "data" / "ugm_news.duckdb"


def main() -> None:
    # Gabung metadata: topik inti (keywords.py) + tema lengkap (kepmen_sdg.py)
    meta = {}
    for topik_id, m in TOPIK_KEPMEN.items():
        meta[topik_id] = dict(m)
        meta[topik_id]["keywords"] = KEYWORDS.get(topik_id, [])
    for topik_id, m in TEMA_KEPMEN_LENGKAP.items():
        meta[topik_id] = dict(m)  # sudah punya keywords + sdg

    con = duckdb.connect(str(DB))
    berita = con.execute("SELECT url, judul, deskripsi, tanggal FROM berita").fetchdf()

    rows = []
    for _, r in berita.iterrows():
        t = f"{r['judul'] or ''} {r['deskripsi'] or ''}".lower()
        for topik_id, m in meta.items():
            # Keyword <= 5 huruf rawan false positive substring (mis. "paten"
            # match "kabupaten", "esd" match kata lain) — pakai word boundary.
            if any(
                re.search(
                    rf"\b{re.escape(kw)}\b" if len(kw) <= 5 else re.escape(kw), t
                )
                for kw in m["keywords"]
            ):
                rows.append(
                    {
                        "url": r["url"],
                        "topik": topik_id,
                        "dampak": m["dampak"],
                        "topik_kepmen": m["topik_kepmen"],
                        "sdg": "|".join(str(s) for s in m["sdg"]) or None,
                    }
                )
    df = pd.DataFrame(rows)

    # -- berita_kepmen_all: url–topik (sdg sebagai string '13|14|15') --
    con.execute("DROP TABLE IF EXISTS berita_kepmen_all")
    con.execute("DROP TABLE IF EXISTS berita_sdg_all")
    con.execute("DROP TABLE IF EXISTS ringkasan_topik_all")
    con.execute("DROP TABLE IF EXISTS ringkasan_pilar")
    con.execute("DROP TABLE IF EXISTS ringkasan_pilar_tahun")
    con.execute("DROP TABLE IF EXISTS ringkasan_sdg_all")
    con.execute("CREATE TABLE berita_kepmen_all (url VARCHAR, topik VARCHAR, "
                "dampak VARCHAR, topik_kepmen VARCHAR, sdg VARCHAR)")
    con.execute("CREATE TABLE berita_sdg_all (url VARCHAR, sdg INTEGER)")
    con.execute("CREATE TABLE ringkasan_topik_all (topik VARCHAR, dampak VARCHAR, "
                "topik_kepmen VARCHAR, sdg VARCHAR, jumlah_berita BIGINT)")
    con.execute("CREATE TABLE ringkasan_pilar (dampak VARCHAR, jumlah_berita BIGINT)")
    con.execute("CREATE TABLE ringkasan_pilar_tahun (dampak VARCHAR, tahun VARCHAR, "
                "jumlah_berita BIGINT)")
    con.execute("CREATE TABLE ringkasan_sdg_all (sdg INTEGER, nama_sdg VARCHAR, "
                "jumlah_berita BIGINT)")

    if len(df):
        con.executemany(
            "INSERT INTO berita_kepmen_all VALUES (?, ?, ?, ?, ?)",
            df.itertuples(index=False, name=None),
        )

        # -- berita_sdg_all: url–sdg dedup (pakai info sdg per topik) --
        sdg_rows = []
        for _, r in df.iterrows():
            for s in str(r["sdg"] or "").split("|"):
                if s:
                    sdg_rows.append((r["url"], int(s)))
        df_sdg = pd.DataFrame(sdg_rows, columns=["url", "sdg"]).drop_duplicates()
        con.executemany(
            "INSERT INTO berita_sdg_all VALUES (?, ?)",
            df_sdg.itertuples(index=False, name=None),
        )

        # -- ringkasan_topik_all (semua 14 tema; jumlah 0 untuk yang tak ada match,
        #    mis. pengajaran_pembelajaran — biar dashboard sinkron 14 topik) --
        hitung = df.groupby("topik")["url"].nunique()
        ring_topik_rows = []
        for topik_id, m in meta.items():
            ring_topik_rows.append(
                {
                    "topik": topik_id,
                    "dampak": m["dampak"],
                    "topik_kepmen": m["topik_kepmen"],
                    "sdg": "|".join(str(s) for s in m["sdg"]) or None,
                    "jumlah_berita": int(hitung.get(topik_id, 0)),
                }
            )
        ring_topik = (
            pd.DataFrame(ring_topik_rows)
            .sort_values("jumlah_berita", ascending=False)
        )
        con.executemany(
            "INSERT INTO ringkasan_topik_all VALUES (?, ?, ?, ?, ?)",
            ring_topik.itertuples(index=False, name=None),
        )

        # -- ringkasan_pilar --
        ring_pilar = (
            df.groupby("dampak")["url"].nunique().reset_index(name="jumlah_berita")
        )
        con.executemany(
            "INSERT INTO ringkasan_pilar VALUES (?, ?)",
            ring_pilar.itertuples(index=False, name=None),
        )

        # -- ringkasan_pilar_tahun --
        df_t = df.merge(
            berita[["url", "tanggal"]], on="url", how="left"
        )
        df_t["tahun"] = df_t["tanggal"].str[:4]
        ring_tahun = (
            df_t.dropna(subset=["tahun"])
            .groupby(["dampak", "tahun"])["url"]
            .nunique()
            .reset_index(name="jumlah_berita")
        )
        con.executemany(
            "INSERT INTO ringkasan_pilar_tahun VALUES (?, ?, ?)",
            ring_tahun.itertuples(index=False, name=None),
        )

        # -- ringkasan_sdg_all --
        df_sdg["nama_sdg"] = df_sdg["sdg"].map(SDG_NAMA)
        ring_sdg = (
            df_sdg.groupby(["sdg", "nama_sdg"])["url"]
            .nunique()
            .reset_index(name="jumlah_berita")
            .sort_values("jumlah_berita", ascending=False)
        )
        con.executemany(
            "INSERT INTO ringkasan_sdg_all VALUES (?, ?, ?)",
            ring_sdg.itertuples(index=False, name=None),
        )

    n_berita = df["url"].nunique() if len(df) else 0
    con.close()
    print(f"Baris url–tema: {len(df)}")
    print(f"Berita unik yang match ≥1 tema: {n_berita} / {len(berita)}")
    print("Tabel baru: berita_kepmen_all, berita_sdg_all, ringkasan_topik_all, "
          "ringkasan_pilar, ringkasan_pilar_tahun, ringkasan_sdg_all")


if __name__ == "__main__":
    main()
