"""Tag tema Kepmen manual untuk berita yang tidak tertangkap keyword ("Berita tanpa match tema").

Disimpan di tabel SENDIRI `berita_tema_manual` (kolom sama dengan berita_berita_kepmen_all:
url, topik, dampak, topik_kepmen, sdg), bukan di tabel pipeline yang ditulis ulang tiap run.
Dampak & klaster SDG diambil dari pemetaan resmi tema (kepmen_sdg.py), jadi berita yang ditandai
langsung ikut dihitung di mode Dampak DAN Dampak x SDGs. StoryService menggabungkan tabel ini saat
memuat frame; tambah/hapus memperbarui frame di cache supaya angka berubah seketika. Hanya berita
yang belum punya tema sama sekali yang bisa ditandai.
"""
from __future__ import annotations

from datetime import datetime
from typing import Any

import pandas as pd
from sqlalchemy import text
from sqlalchemy.engine import Engine

from app.domain.source import kepmen
from app.services.story import StoryFrames, StoryService

TABEL = "berita_tema_manual"
MAX_PAGE_SIZE = 50


class TagError(ValueError):
    """Permintaan tag tidak valid (400)."""


def ensure_schema(engine: Engine) -> None:
    with engine.begin() as conn:
        conn.execute(text(f"""
            CREATE TABLE IF NOT EXISTS {TABEL} (
                url VARCHAR(500) NOT NULL,
                topik VARCHAR(64) NOT NULL,
                dampak VARCHAR(32) NOT NULL,
                topik_kepmen VARCHAR(255) NOT NULL,
                sdg VARCHAR(64),
                oleh VARCHAR(254),
                created_at TIMESTAMP NOT NULL,
                PRIMARY KEY (url, topik)
            )
        """))


def baris_tema(url: str, topik: str) -> dict[str, Any]:
    """Satu baris setara berita_berita_kepmen_all untuk tema resmi `topik`."""
    meta = kepmen().TOPIK_KEPMEN_ALL[topik]
    return {"url": url, "topik": topik, "dampak": meta["dampak"], "topik_kepmen": meta["topik_kepmen"],
            "sdg": "|".join(str(int(s)) for s in meta.get("sdg", []))}


def sdg_dari(rows: pd.DataFrame) -> pd.DataFrame:
    """Baris (url, sdg) dari kolom sdg "1|4|10" -- padanan berita_berita_sdg_all untuk tag manual."""
    pasang = [(u, int(s)) for u, sdg in zip(rows["url"], rows["sdg"].fillna("")) for s in str(sdg).split("|") if s.strip()]
    return pd.DataFrame(pasang, columns=["url", "sdg"])


def _aman(url: str) -> str | None:
    url = (url or "").strip()
    return url if url.lower().startswith(("https://", "http://")) else None


def tanpa_tema(fr: StoryFrames, page: int = 1, page_size: int = 5, q: str = "",
               year_from: str | None = None, year_to: str | None = None,
               units: tuple[str, ...] = ()) -> dict[str, Any]:
    """Berita (dalam rentang tahun/unit) yang tidak masuk tema Kepmen mana pun, terbaru lebih dulu."""
    if page < 1 or not 1 <= page_size <= MAX_PAGE_SIZE:
        raise TagError(f"page >= 1 dan page_size 1-{MAX_PAGE_SIZE}")
    b = fr.berita.assign(tahun=fr.berita["tanggal"].fillna("").astype(str).str[:4])
    if year_from:
        b = b[b["tahun"] >= year_from]
    if year_to:
        b = b[b["tahun"] <= year_to]
    if units:
        b = b[b["url"].isin(set(fr.uk.loc[fr.uk["unit_kerja"].isin(units), "url"]))]
    b = b[~b["url"].isin(set(fr.bk["url"]))]
    q = (q or "").strip()[:100].lower()
    if q:
        b = b[b["judul"].fillna("").str.lower().str.contains(q, regex=False)
              | b["url"].str.lower().str.contains(q, regex=False)]
    b = b.sort_values(["tanggal", "url"], ascending=[False, True], kind="stable")
    halaman = b.iloc[(page - 1) * page_size: page * page_size]
    return {
        "page": page, "page_size": page_size, "total": int(len(b)),
        "rows": [{"url": r["url"], "tautan": _aman(r["url"]), "judul": r["judul"] or "",
                  "tanggal": str(r["tanggal"] or "")[:10], "deskripsi": str(r.get("deskripsi") or "")[:240]}
                 for r in halaman.to_dict("records")],
    }


def _validasi(fr: StoryFrames, url: str, topiks: Any) -> list[str]:
    if url not in set(fr.berita["url"]):
        raise TagError("Berita tidak ditemukan.")
    meta = kepmen().TOPIK_KEPMEN_ALL
    if not isinstance(topiks, list) or not topiks:
        raise TagError("Pilih minimal satu tema.")
    daftar = sorted({str(t) for t in topiks})
    if any(t not in meta for t in daftar):
        raise TagError("Tema tidak dikenal.")
    return daftar


def tandai(engine: Engine, fr: StoryFrames, url: str, topiks: Any, oleh: str) -> dict[str, Any]:
    daftar = _validasi(fr, url, topiks)
    if url in set(fr.bk["url"]):
        raise TagError("Berita ini sudah punya tema.")
    now = datetime.now()
    rows = [baris_tema(url, t) for t in daftar]
    with engine.begin() as conn:
        conn.execute(text(f"""
            INSERT INTO {TABEL} (url, topik, dampak, topik_kepmen, sdg, oleh, created_at)
            VALUES (:url, :topik, :dampak, :topik_kepmen, :sdg, :oleh, :t)
        """), [{**r, "oleh": oleh, "t": now} for r in rows])
    baru = pd.DataFrame(rows)
    with StoryService._lock:  # frame di cache ikut diperbarui (dibagi semua permintaan)
        fr.bk = pd.concat([fr.bk, baru[["url", "topik", "dampak", "topik_kepmen"]]], ignore_index=True)
        fr.bs = pd.concat([fr.bs, sdg_dari(baru)], ignore_index=True).drop_duplicates(["url", "sdg"])
    label = kepmen().LABEL_TOPIC_ALL
    return {"url": url, "topiks": daftar,
            "message": f"Ditandai tema {', '.join(label.get(t, t) for t in daftar)}."}


def batalkan(engine: Engine, fr: StoryFrames, url: str) -> dict[str, Any]:
    """Hapus tag tema MANUAL sebuah berita (tema dari pipeline tidak tersentuh)."""
    with engine.begin() as conn:
        manual = [r[0] for r in conn.execute(text(f"SELECT topik FROM {TABEL} WHERE url = :u"), {"u": url}).all()]
        if not manual:
            raise TagError("Berita ini tidak punya tag tema manual.")
        conn.execute(text(f"DELETE FROM {TABEL} WHERE url = :u"), {"u": url})
    with StoryService._lock:
        fr.bk = fr.bk[~((fr.bk["url"] == url) & fr.bk["topik"].isin(manual))].reset_index(drop=True)
        # SDG klaster berita ini hanya berasal dari tag manual (berita tanpa tema tidak punya SDG pipeline).
        fr.bs = fr.bs[fr.bs["url"] != url].reset_index(drop=True)
    return {"url": url, "topiks": manual, "message": "Tag tema manual dibatalkan."}
