"""Tag SDG manual untuk berita yang tidak tertangkap keyword ("Berita tanpa tanda SDG").

Disimpan di tabel SENDIRI `berita_sdg_manual`, bukan di berita_sitemap_sdg: pipeline
tag_sdg_langsung.py menulis ulang (DROP + CREATE) berita_sitemap_sdg setiap dijalankan, jadi
tag manual di sana akan hilang. StoryService menggabungkan keduanya saat memuat frame, dan
setiap tambah/hapus langsung memperbarui frame di cache supaya angka SDG ikut berubah tanpa
menunggu cache kedaluwarsa. Hanya berita yang belum punya SDG sama sekali yang bisa ditandai.
"""
from __future__ import annotations

from datetime import datetime
from typing import Any

import pandas as pd
from sqlalchemy import text
from sqlalchemy.engine import Engine

from app.services.story import StoryFrames, StoryService

TABEL = "berita_sdg_manual"
MAX_PAGE_SIZE = 50


class TagError(ValueError):
    """Permintaan tag tidak valid (400)."""


def ensure_schema(engine: Engine) -> None:
    with engine.begin() as conn:
        conn.execute(text(f"""
            CREATE TABLE IF NOT EXISTS {TABEL} (
                url VARCHAR(500) NOT NULL,
                sdg INTEGER NOT NULL,
                oleh VARCHAR(254),
                created_at TIMESTAMP NOT NULL,
                PRIMARY KEY (url, sdg)
            )
        """))


def _aman(url: str) -> str | None:
    url = (url or "").strip()
    return url if url.lower().startswith(("https://", "http://")) else None


def _url_bersih(s: pd.Series) -> pd.Series:
    return s.astype(str).str.split("?").str[0].str.rstrip("/")


def belum_bertanda(fr: StoryFrames, page: int = 1, page_size: int = 5, q: str = "",
                   year_from: str | None = None, year_to: str | None = None,
                   units: tuple[str, ...] = ()) -> dict[str, Any]:
    """Berita sitemap (dalam rentang tahun/unit) yang belum punya SDG, terbaru lebih dulu."""
    if page < 1 or not 1 <= page_size <= MAX_PAGE_SIZE:
        raise TagError(f"page >= 1 dan page_size 1-{MAX_PAGE_SIZE}")
    sm = fr.sitemap.assign(tahun=fr.sitemap["lastmod"].fillna("").astype(str).str[:4])
    if year_from:
        sm = sm[sm["tahun"] >= year_from]
    if year_to:
        sm = sm[sm["tahun"] <= year_to]
    if units:
        unit_urls = set(fr.uk.loc[fr.uk["unit_kerja"].isin(units), "url"])
        sm = sm[_url_bersih(sm["url"]).isin(unit_urls)]
    sm = sm[~sm["url"].isin(set(fr.ss["url"]))]
    judul = dict(zip(_url_bersih(fr.berita["url"]), fr.berita["judul"].fillna("")))
    sm = sm.assign(judul=_url_bersih(sm["url"]).map(judul).fillna(""))
    q = (q or "").strip()[:100].lower()
    if q:
        sm = sm[sm["judul"].str.lower().str.contains(q, regex=False) | sm["url"].str.lower().str.contains(q, regex=False)]
    sm = sm.sort_values(["lastmod", "url"], ascending=[False, True], kind="stable")
    halaman = sm.iloc[(page - 1) * page_size: page * page_size]
    return {
        "page": page, "page_size": page_size, "total": int(len(sm)),
        "rows": [{"url": r["url"], "tautan": _aman(r["url"]), "judul": r["judul"],
                  "tanggal": str(r["lastmod"] or "")[:10]} for r in halaman.to_dict("records")],
    }


def _validasi(fr: StoryFrames, url: str, sdgs: Any) -> list[int]:
    if url not in set(fr.sitemap["url"]):
        raise TagError("Berita tidak ditemukan di sitemap.")
    try:
        daftar = sorted({int(s) for s in (sdgs or [])})
    except (TypeError, ValueError) as exc:
        raise TagError("SDG harus angka 1-17.") from exc
    if not daftar or any(s < 1 or s > 17 for s in daftar):
        raise TagError("Pilih minimal satu SDG (1-17).")
    return daftar


def tandai(engine: Engine, fr: StoryFrames, url: str, sdgs: Any, oleh: str) -> dict[str, Any]:
    daftar = _validasi(fr, url, sdgs)
    if url in set(fr.ss["url"]):
        raise TagError("Berita ini sudah bertanda SDG.")
    now = datetime.now()
    with engine.begin() as conn:
        conn.execute(text(f"INSERT INTO {TABEL} (url, sdg, oleh, created_at) VALUES (:u, :s, :o, :t)"),
                     [{"u": url, "s": s, "o": oleh, "t": now} for s in daftar])
    with StoryService._lock:  # frame di cache ikut diperbarui (dibagi semua permintaan)
        fr.ss = pd.concat([fr.ss, pd.DataFrame({"url": url, "sdg": daftar})], ignore_index=True)
    return {"url": url, "sdgs": daftar, "message": f"Ditandai SDG {', '.join(map(str, daftar))}."}


def batalkan(engine: Engine, fr: StoryFrames, url: str) -> dict[str, Any]:
    """Hapus tag MANUAL sebuah berita (tag otomatis dari pipeline tidak tersentuh)."""
    with engine.begin() as conn:
        manual = [int(r[0]) for r in conn.execute(text(f"SELECT sdg FROM {TABEL} WHERE url = :u"), {"u": url}).all()]
        if not manual:
            raise TagError("Berita ini tidak punya tag SDG manual.")
        conn.execute(text(f"DELETE FROM {TABEL} WHERE url = :u"), {"u": url})
    with StoryService._lock:
        fr.ss = fr.ss[~((fr.ss["url"] == url) & fr.ss["sdg"].isin(manual))].reset_index(drop=True)
    return {"url": url, "sdgs": manual, "message": "Tag SDG manual dibatalkan."}
