"""Tagging LANGSUNG seluruh URL sitemap ugm.ac.id -> SDG (tanpa tema Kepmen).

Mode dashboard "SDGs saja": SEMUA 32.130 URL berita (sitemap baseline) ditandai
ke 17 SDG. Teks yang dicocokkan:
  - kata-kata slug URL (path setelah /id/berita/ atau /en/news/, dipisah '-'),
    untuk URL yang BELUM di-fetch — kualitas kasar;
  - + judul & deskripsi dari tabel `berita` (URL yang sudah di-fetch) + isi
    lengkap artikel kalau kolom `isi` sudah ada (scripts/fetch_backlog.py).

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

import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parent))
from db import column_exists, get_engine, read_sql_retry, t, with_retry  # noqa: E402
from kepmen_sdg import SDG_NAMA  # noqa: E402
from sdg_keywords import SDG_KEYWORDS  # noqa: E402

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
    engine = get_engine()
    sitemap = read_sql_retry(engine, f"SELECT url, lastmod FROM `{t('sitemap')}`", label="baca sitemap")
    # isi lengkap (scripts/fetch_backlog.py) baru ada setelah backlog itu
    # pernah dijalankan -- cek dulu, fallback ke judul+deskripsi kalau belum.
    has_isi = column_exists(engine, t("berita"), "isi")
    kolom = "url, judul, deskripsi" + (", isi" if has_isi else "")
    berita = read_sql_retry(engine, f"SELECT {kolom} FROM `{t('berita')}`", label="baca berita")

    # teks tambahan dari tabel berita (url bersih -> judul + deskripsi + isi)
    berita["url_b"] = berita["url"].map(url_bersih)

    def teks_row(r) -> str:
        dasar = f"{r['judul'] or ''} {r['deskripsi'] or ''}"
        return f"{dasar} {r['isi'] or ''}" if has_isi else dasar

    teks_berita = {r["url_b"]: teks_row(r).lower() for _, r in berita.iterrows()}

    compiled = compile_sdg()

    rows = []
    for _, r in sitemap.iterrows():
        u = r["url"]
        teks = " ".join(slug_words(u))
        teks_ber = teks_berita.get(url_bersih(u), "")
        # NB: nama variabel "teks_gab" (bukan "t") -- "t" sudah dipakai
        # sebagai helper prefix tabel (db.t), jangan di-shadow di sini.
        teks_gab = f"{teks} {teks_ber}".lower()
        for sdg, rx in compiled.items():
            if any(p.search(teks_gab) for p in rx):
                rows.append({"url": u, "sdg": sdg})

    df = pd.DataFrame(rows, columns=["url", "sdg"])
    n_tertag = df["url"].nunique() if len(df) else 0

    outputs: dict[str, pd.DataFrame] = {"sitemap_sdg": df}

    if len(df):
        # ringkasan per SDG (url unik)
        ring = (
            df.groupby("sdg")["url"].nunique().reset_index(name="jumlah_berita")
        )
        ring["nama_sdg"] = ring["sdg"].map(SDG_NAMA)
        ring = ring[["sdg", "nama_sdg", "jumlah_berita"]].sort_values(
            "jumlah_berita", ascending=False
        )
        outputs["ringkasan_sdg_sitemap"] = ring

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
        outputs["ringkasan_sdg_sitemap_tahun"] = ring_t
    else:
        outputs["ringkasan_sdg_sitemap"] = pd.DataFrame(columns=["sdg", "nama_sdg", "jumlah_berita"])
        outputs["ringkasan_sdg_sitemap_tahun"] = pd.DataFrame(
            columns=["sdg", "nama_sdg", "tahun", "jumlah_berita"])

    gagal_tabel = []
    for name, out_df in outputs.items():
        ok, _ = with_retry(
            lambda out_df=out_df, name=name: out_df.to_sql(t(name), engine, if_exists="replace", index=False),
            label=f"tulis {name}",
        )
        if not ok:
            gagal_tabel.append(name)

    print(f"Pasangan url-sdg: {len(df)}")
    print(f"URL bertanda >=1 SDG: {n_tertag} / {len(sitemap)} "
          f"({100 * n_tertag / len(sitemap):.1f}%)")
    if gagal_tabel:
        print(f"PERINGATAN: tabel gagal ditulis setelah retry: {', '.join(gagal_tabel)}")
    print("Tabel: " + ", ".join(outputs.keys()))


if __name__ == "__main__":
    main()
