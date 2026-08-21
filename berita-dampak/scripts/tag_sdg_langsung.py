"""Tagging LANGSUNG seluruh URL sitemap ugm.ac.id -> SDG (tanpa tema Kepmen).

Mode dashboard "SDGs saja": SEMUA 32.130 URL berita (sitemap baseline) ditandai
ke 17 SDG. Teks yang dicocokkan:
  - kata-kata slug URL (path setelah /id/berita/ atau /en/news/, dipisah '-'),
    untuk URL yang BELUM di-fetch (27.343) — kualitas kasar;
  - + judul & deskripsi dari tabel `berita` (4.787 URL yang sudah di-fetch).

Konvensi keyword: <= 5 huruf -> word-boundary (\\b..\\b); lebih panjang ->
substring match (sama dengan tag_kepmen_all.py). Satu URL bisa masuk beberapa
SDG (multi-SDG by design).

Output (idempoten, DROP + recreate):
  - sitemap_sdg              : url, sdg (pasangan url-sdg)
  - ringkasan_sdg_sitemap    : sdg, nama_sdg, jumlah_berita (url unik)
  - ringkasan_sdg_sitemap_tahun : sdg, nama_sdg, tahun, jumlah_berita

Jalankan (dari folder berita-dampak):
  ../venv/Scripts/python.exe scripts/tag_sdg_langsung.py
"""

import re
import sys
from pathlib import Path

import duckdb
import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parent))
from kepmen_sdg import SDG_NAMA  # noqa: E402
from sdg_keywords import SDG_KEYWORDS  # noqa: E402

DB = Path(__file__).resolve().parents[1] / "data" / "ugm_news.duckdb"

LANG = ("id", "en")


def url_bersih(url: str) -> str:
    """Bentuk bersih URL: buang query (?...) dan trailing slash (konvensi normalisasi)."""
    return url.split("?")[0].rstrip("/")


def slug_words(url: str) -> list[str]:
    """Kata-kata dari slug URL (setelah /id/berita/ atau /en/news/)."""
    u = url_bersih(url)
    m = re.search(r"/(?:id|en)/(?:berita|news)/([^/]+)/?$", u)
    if not m:
        return []
    slug = m.group(1)
    # buang angka murni (id post, tahun) dan pecah '-' jadi kata
    return [w for w in re.split(r"[-_]+", slug.lower()) if w and not w.isdigit()]


def kw_regex(kw: str) -> re.Pattern:
    return re.compile(rf"\b{re.escape(kw)}\b" if len(kw) <= 5 else re.escape(kw))


def compile_sdg():
    """Satu-dua regex per SDG (alternation) — jauh lebih cepat dari regex per keyword."""
    compiled = {}
    for sdg, kws in SDG_KEYWORDS.items():
        pendek = [re.escape(k) for k in kws if len(k) <= 5]
        panjang = [re.escape(k) for k in kws if len(k) > 5]
        rx = []
        if pendek:
            rx.append(re.compile(rf"\b(?:{'|'.join(pendek)})\b"))
        if panjang:
            rx.append(re.compile("|".join(panjang)))
        compiled[sdg] = rx
    return compiled


def main() -> None:
    con = duckdb.connect(str(DB))
    sitemap = con.execute("SELECT url, lastmod FROM sitemap").fetchdf()
    berita = con.execute("SELECT url, judul, deskripsi FROM berita").fetchdf()

    # teks tambahan dari tabel berita (url bersih -> judul + deskripsi)
    berita["url_b"] = berita["url"].map(url_bersih)
    teks_berita = {
        r["url_b"]: f"{r['judul'] or ''} {r['deskripsi'] or ''}".lower()
        for _, r in berita.iterrows()
    }

    compiled = compile_sdg()

    rows = []
    for _, r in sitemap.iterrows():
        u = r["url"]
        teks = " ".join(slug_words(u))
        teks_ber = teks_berita.get(url_bersih(u), "")
        t = f"{teks} {teks_ber}".lower()
        for sdg, rx in compiled.items():
            if any(p.search(t) for p in rx):
                rows.append({"url": u, "sdg": sdg})

    df = pd.DataFrame(rows)
    n_tertag = df["url"].nunique() if len(df) else 0

    # ---- tabel output ----
    con.execute("DROP TABLE IF EXISTS sitemap_sdg")
    con.execute("DROP TABLE IF EXISTS ringkasan_sdg_sitemap")
    con.execute("DROP TABLE IF EXISTS ringkasan_sdg_sitemap_tahun")
    con.execute("CREATE TABLE sitemap_sdg (url VARCHAR, sdg INTEGER)")
    con.execute("CREATE TABLE ringkasan_sdg_sitemap (sdg INTEGER, nama_sdg VARCHAR, "
                "jumlah_berita BIGINT)")
    con.execute("CREATE TABLE ringkasan_sdg_sitemap_tahun (sdg INTEGER, nama_sdg VARCHAR, "
                "tahun VARCHAR, jumlah_berita BIGINT)")

    if len(df):
        con.executemany("INSERT INTO sitemap_sdg VALUES (?, ?)",
                        df.itertuples(index=False, name=None))

        # ringkasan per SDG (url unik)
        ring = (
            df.groupby("sdg")["url"].nunique().reset_index(name="jumlah_berita")
        )
        ring["nama_sdg"] = ring["sdg"].map(SDG_NAMA)
        ring = ring[["sdg", "nama_sdg", "jumlah_berita"]].sort_values(
            "jumlah_berita", ascending=False
        )
        con.executemany("INSERT INTO ringkasan_sdg_sitemap VALUES (?, ?, ?)",
                        ring.itertuples(index=False, name=None))

        # ringkasan per SDG per tahun (lastmod sitemap)
        df_t = df.merge(sitemap[["url", "lastmod"]], on="url", how="left")
        df_t["tahun"] = df_t["lastmod"].str[:4]
        ring_t = (
            df_t.dropna(subset=["tahun"])
            .groupby(["sdg", "tahun"])["url"]
            .nunique()
            .reset_index(name="jumlah_berita")
        )
        ring_t["nama_sdg"] = ring_t["sdg"].map(SDG_NAMA)
        ring_t = ring_t[["sdg", "nama_sdg", "tahun", "jumlah_berita"]]
        con.executemany("INSERT INTO ringkasan_sdg_sitemap_tahun VALUES (?, ?, ?, ?)",
                        ring_t.itertuples(index=False, name=None))

    con.close()
    print(f"Pasangan url-sdg: {len(df)}")
    print(f"URL bertanda >=1 SDG: {n_tertag} / {len(sitemap)} "
          f"({100 * n_tertag / len(sitemap):.1f}%)")
    print("Tabel baru: sitemap_sdg, ringkasan_sdg_sitemap, ringkasan_sdg_sitemap_tahun")


if __name__ == "__main__":
    main()
