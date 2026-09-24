"""Hitung jumlah berita per keyword SDG -> tabel berita_ringkasan_keyword_sdg.

Dipakai bagian SDGs di web ("Peta sebaran keyword SDG"). Teks & aturan pencocokan
DIIMPOR dari tag_sdg_langsung.py (slug URL + judul + deskripsi + isi lengkap bila ada;
keyword <= 5 huruf = kata utuh, lebih panjang = substring), jadi hitungannya konsisten
dengan tag SDG yang tampil di dashboard.

Yang dihitung: untuk tiap SDG, dari URL yang SUDAH bertanda SDG itu di berita_sitemap_sdg,
berapa URL yang teksnya memuat tiap keyword. Satu URL bisa memuat beberapa keyword, jadi
jumlah per keyword tidak dijumlahkan menjadi total SDG.

Skrip ini hanya membaca berita_sitemap / berita_berita / berita_sitemap_sdg dan menulis
ulang tabel ringkasannya sendiri (idempoten). Jalankan setelah tag_sdg_langsung.py:
  ../venv/Scripts/python.exe scripts/hitung_keyword_sdg.py
"""
from __future__ import annotations

import sys
from collections import Counter
from datetime import datetime
from pathlib import Path

import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parent))
from db import column_exists, get_engine, read_sql_retry, t, with_retry  # noqa: E402
from sdg_keywords import SDG_KEYWORDS  # noqa: E402
from tag_sdg_langsung import kw_regex, slug_words, url_bersih  # noqa: E402


def main() -> None:
    engine = get_engine()
    sitemap = read_sql_retry(engine, f"SELECT url FROM `{t('sitemap')}`", label="baca sitemap")
    tag = read_sql_retry(engine, f"SELECT url, sdg FROM `{t('sitemap_sdg')}`", label="baca sitemap_sdg")
    has_isi = column_exists(engine, t("berita"), "isi")
    kolom = "url, judul, deskripsi" + (", isi" if has_isi else "")
    berita = read_sql_retry(engine, f"SELECT {kolom} FROM `{t('berita')}`", label="baca berita")

    teks_berita = {}
    for r in berita.to_dict("records"):
        dasar = f"{r['judul'] or ''} {r['deskripsi'] or ''}"
        teks_berita[url_bersih(r["url"])] = (f"{dasar} {r.get('isi') or ''}" if has_isi else dasar).lower()

    teks = {u: f"{' '.join(slug_words(u))} {teks_berita.get(url_bersih(u), '')}".lower() for u in sitemap["url"]}
    url_per_sdg = tag.groupby(tag["sdg"].astype(int))["url"].apply(set).to_dict()

    rows = []
    for sdg, kws in SDG_KEYWORDS.items():
        sdg = int(sdg)
        daftar = kws["keywords"] if isinstance(kws, dict) else kws
        urls = [u for u in url_per_sdg.get(sdg, ()) if u in teks]
        hitung: Counter = Counter()
        for kw in daftar:
            pola = kw_regex(kw)
            hitung[kw] = sum(1 for u in urls if pola.search(teks[u]))
        for kw in daftar:
            rows.append({"sdg": sdg, "keyword": kw, "jumlah_berita": int(hitung[kw])})
        print(f"SDG {sdg:>2}: {len(urls):>6} berita, {sum(1 for v in hitung.values() if v)} keyword terpakai")

    out = pd.DataFrame(rows, columns=["sdg", "keyword", "jumlah_berita"])
    out["dihitung_at"] = datetime.now()
    ok, _ = with_retry(lambda: out.to_sql(t("ringkasan_keyword_sdg"), engine, if_exists="replace", index=False),
                       label="tulis ringkasan_keyword_sdg")
    print(f"{'OK' if ok else 'GAGAL'}: {len(out)} baris -> {t('ringkasan_keyword_sdg')}")


if __name__ == "__main__":
    main()
