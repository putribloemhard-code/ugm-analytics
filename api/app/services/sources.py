"""Bagian "Sumber" halaman Dampak: dari mana angka berasal, dan daftar berita yang memuat dampak.

Dua sumber publik yang dipakai sekarang:
- Berita ugm.ac.id: sitemap + RSS di-scrape pipeline berita-dampak (tabel berita_*).
- Web program studi: halaman kurikulum publik tiap prodi, dikurasi ke
  matkul-sustainability/data/Deskripsi Matkul Kepmen.csv. Seharusnya dari sistem kurikulum
  internal UGM, tetapi aksesnya belum ada -- ditandai jelas di payload (`internal`).

Dihitung dari StoryFrames yang sudah di-cache StoryService (frame yang sama dengan /story),
bukan query baru: `IN (subquery)` tanpa indeks di tabel berita butuh 3-15 detik per permintaan,
sedangkan dari frame di memori hanya milidetik. Semua angka dihitung dari data, tidak ada angka tetap.
"""
from __future__ import annotations

from typing import Any

from app.domain.source import kepmen
from app.services.matkul import STATUS_TAK_DINILAI, TEMA_INDIKATOR, MatkulFrames
from app.services.story import StoryFrames

PILAR = ("Sosial", "Ekonomi", "Lingkungan")
MAX_PAGE_SIZE = 50


def _aman(url: str) -> str | None:
    """Tautan hanya dikirim bila http(s) -- nilai dari DB tidak boleh jadi javascript: di href."""
    url = (url or "").strip()
    return url if url.lower().startswith(("https://", "http://")) else None


def _urut_pilar(p: str) -> int:
    return PILAR.index(p) if p in PILAR else len(PILAR)


def ringkasan_berita(fr: StoryFrames) -> dict[str, Any]:
    b = fr.berita
    tanggal = b["tanggal"].dropna().astype(str)
    tanggal = tanggal[tanggal.str.match(r"^\d{4}")]
    per_pilar = fr.bk.groupby("dampak")["url"].nunique()
    inggris = int(b["url"].astype(str).str.contains("/en/", regex=False).sum())
    return {
        "situs": "ugm.ac.id",
        "sitemap": int(fr.sitemap["url"].nunique()),
        "diambil": int(len(b)),
        "berdampak": int(fr.bk["url"].nunique()),
        "rss": int((b["sumber"] == "rss").sum()) if "sumber" in b else 0,
        "bahasa": {"id": int(len(b)) - inggris, "en": inggris},
        "tahun_awal": tanggal.min()[:4] if len(tanggal) else None,
        "tahun_akhir": tanggal.max()[:4] if len(tanggal) else None,
        "diperbarui": fr.data_as_of,
        "per_pilar": [{"pilar": p, "jumlah": int(per_pilar.get(p, 0))} for p in PILAR],
    }


def ringkasan_mata_kuliah(mf: MatkulFrames | None) -> dict[str, Any]:
    if mf is None:
        return {"tersedia": False}
    b = mf.baris
    ada_nama = b[b["nama_mk"] != ""]
    meta = kepmen().TOPIK_KEPMEN_ALL
    t = mf.mk_tema
    pilar_mk = t.assign(pilar=t["tema"].map(lambda x: meta[x]["dampak"])).groupby("pilar")["nama_mk"].nunique()
    return {
        "tersedia": True,
        "baris": int(len(b)),
        "prodi": int(b.loc[b["prodi"] != "", "prodi"].nunique()),
        "fakultas": int(b.loc[b["fakultas"] != "", "fakultas"].nunique()),
        "mk_unik": int(ada_nama["nama_mk"].str.lower().nunique()),
        "mk_belum_dinilai": int(ada_nama.loc[ada_nama["status"] == STATUS_TAK_DINILAI, "nama_mk"].str.lower().nunique()),
        "berdampak": int(t["nama_mk"].nunique()),
        "indikator_resmi": int((t["tema"] == TEMA_INDIKATOR).sum()),
        "per_pilar": [{"pilar": p, "jumlah": int(pilar_mk.get(p, 0))} for p in PILAR],
    }


def ringkasan_sumber(fr: StoryFrames) -> dict[str, Any]:
    return {
        "berita": ringkasan_berita(fr),
        "mata_kuliah": ringkasan_mata_kuliah(fr.matkul),
        # Sumber internal yang semestinya dipakai tetapi belum bisa diakses -- ditampilkan jujur.
        "internal": [{
            "nama": "Sistem kurikulum internal UGM",
            "status": "Belum ada akses",
            "pengganti": "Web program studi (publik)",
        }],
    }


def berita_berdampak(fr: StoryFrames, page: int = 1, page_size: int = 10, q: str = "",
                     pilar: str = "") -> dict[str, Any]:
    """Berita yang memuat minimal satu tema dampak Kepmen: satu baris per berita, tema digabung."""
    if page < 1 or not 1 <= page_size <= MAX_PAGE_SIZE:
        raise ValueError(f"page >= 1 dan page_size 1-{MAX_PAGE_SIZE}")
    if pilar and pilar not in PILAR:
        raise ValueError("pilar tidak dikenal")
    bk = fr.bk if not pilar else fr.bk[fr.bk["dampak"] == pilar]
    b = fr.berita[fr.berita["url"].isin(set(bk["url"]))]
    q = (q or "").strip()[:100]
    if q:
        b = b[b["judul"].fillna("").str.contains(q, case=False, regex=False)]
    b = b.sort_values(["tanggal", "url"], ascending=[False, True], kind="stable")
    total = int(len(b))
    halaman = b.iloc[(page - 1) * page_size: page * page_size]
    label = kepmen().LABEL_TOPIC_ALL
    tag = fr.bk[fr.bk["url"].isin(set(halaman["url"]))]
    tema: dict[str, set[tuple[str, str]]] = {}
    for url, topik, dampak in zip(tag["url"], tag["topik"], tag["dampak"]):
        tema.setdefault(url, set()).add((label.get(topik, topik), dampak))
    rows = []
    for r in halaman.fillna("").to_dict("records"):
        daftar = sorted(tema.get(r["url"], set()))
        rows.append({
            "judul": r["judul"] or r["url"],
            "tautan": _aman(r["url"]),
            "tanggal": str(r["tanggal"])[:10],
            "bahasa": "EN" if "/en/" in r["url"] else "ID",
            "tema": [t for t, _ in daftar],
            "pilar": sorted({p for _, p in daftar}, key=_urut_pilar),
        })
    return {"page": page, "page_size": page_size, "total": total, "rows": rows}
