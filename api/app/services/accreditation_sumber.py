"""Status sumber data resmi + data live untuk item LED/LKPS.

Acuan status yang sah adalah akreditasi/data_source_map.json (Fase 1), BUKAN
`status_ketersediaan` di registry_kebutuhan_data.py (lihat docstring registry poin 7):

- "tersedia"                              -> data ditarik pipeline Fase 2 ke akreditasi_item_tersedia
- "tidak_tersedia" + "akses_data"         -> sumber ada tapi belum bisa diakses sistem; diisi tim
- "tidak_tersedia" + "perlu_penyusunan_manusia" -> narasi/keputusan yang memang ditulis tim penyusun

Tabel hasil pipeline Fase 2 (akreditasi_item_tersedia, akreditasi_publikasi_dosen,
akreditasi_berita_dcse) tidak punya kolom prodi: seluruh sumbernya halaman Prodi MEI
(dcse.fmipa.ugm.ac.id/mei, SINTA dosen MEI). Karena itu data live hanya dipasangkan ke prodi
LIVE_PRODI; prodi lain tetap melihat status peta tetapi tanpa data live.

Tabel-tabel itu bisa belum ada (mis. PostgreSQL produksi yang belum dimigrasi); pembacaan
gagal diperlakukan sebagai "tidak ada data live", bukan error halaman.
"""
from __future__ import annotations

import json
import logging
from functools import lru_cache
from typing import Any

from sqlalchemy import text

from app.domain.source import REPO_ROOT

logger = logging.getLogger(__name__)

MAP_PATH = REPO_ROOT / "akreditasi" / "data_source_map.json"
LIVE_PRODI = "mei"
KATEGORI_LABEL = {
    "tersedia": "Tersedia dari sumber live",
    "akses_data": "Perlu akses data (diisi tim)",
    "penyusunan": "Perlu disusun tim penyusun",
}
# Item yang punya data pendukung live (bukan pengganti field resmi), sesuai sumber_tambahan di peta.
PENDUKUNG_PUBLIKASI = ("lkps_3_c_2", "lkps_3_a_2", "led_b5_dosen_tendik")
PENDUKUNG_BERITA = ("lkps_2_d", "lkps_4_c_2")
MAX_PENDUKUNG = 15


@lru_cache(maxsize=1)
def peta() -> dict[str, dict[str, Any]]:
    """kode_item -> entri peta. Kosong kalau file tidak ada (semua item lalu dianggap akses_data)."""
    try:
        data = json.loads(MAP_PATH.read_text(encoding="utf-8"))
    except FileNotFoundError:
        logger.warning("data_source_map.json tidak ditemukan di %s", MAP_PATH)
        return {}
    return {item["kode_item"]: item for item in data.get("items", [])}


def kategori(item_id: str) -> str:
    entri = peta().get(item_id) or {}
    if entri.get("status") == "tersedia":
        return "tersedia"
    return "penyusunan" if entri.get("jenis_kendala") == "perlu_penyusunan_manusia" else "akses_data"


def info_item(item_id: str) -> dict[str, Any]:
    entri = peta().get(item_id) or {}
    k = kategori(item_id)
    return {
        "kategori": k,
        "kategori_label": KATEGORI_LABEL[k],
        "sumber_asli": entri.get("sumber_asli") or None,
        "catatan": entri.get("catatan_jika_tidak_tersedia") or entri.get("catatan") or None,
        "sumber_tambahan": entri.get("sumber_tambahan") or None,
    }


def _baca(conn, sql: str, params: dict[str, Any] | None = None) -> list[dict[str, Any]]:
    # SAVEPOINT supaya tabel yang belum ada tidak membatalkan transaksi pemanggil (PostgreSQL).
    try:
        with conn.begin_nested():
            return [dict(r) for r in conn.execute(text(sql), params or {}).mappings().all()]
    except Exception:
        logger.info("tabel data live tidak terbaca, dilewati: %s", sql.split("FROM")[1].split()[0])
        return []


def data_live(conn, prodi_id: str) -> dict[str, Any]:
    """Data live untuk prodi ini: {"items": {item_id: {...}}, "publikasi": [...], "berita": [...]}."""
    kosong = {"items": {}, "publikasi": [], "berita": [], "n_publikasi": 0, "n_berita": 0}
    if prodi_id != LIVE_PRODI:
        return kosong
    sel = _baca(conn, """
        SELECT item_id, baris_ke, kolom, nilai, sumber_url, fetched_at
        FROM akreditasi_item_tersedia ORDER BY item_id, baris_ke
    """)
    items: dict[str, dict[str, Any]] = {}
    for r in sel:
        it = items.setdefault(r["item_id"], {"baris": {}, "sumber": [], "fetched_at": None})
        it["baris"].setdefault(int(r["baris_ke"]), {})[r["kolom"]] = r["nilai"] or ""
        if r["sumber_url"] and r["sumber_url"] not in it["sumber"]:
            it["sumber"].append(r["sumber_url"])
        stamp = str(r["fetched_at"] or "")
        if stamp and (it["fetched_at"] is None or stamp > it["fetched_at"]):
            it["fetched_at"] = stamp
    for it in items.values():
        it["rows"] = [it["baris"][b] for b in sorted(it["baris"])]
        del it["baris"]
    publikasi = _baca(conn, """
        SELECT dosen, judul, tahun, sumber, link FROM akreditasi_publikasi_dosen ORDER BY dosen, tahun DESC
    """)
    berita = _baca(conn, """
        SELECT judul, tanggal, url FROM akreditasi_berita_dcse WHERE relevan_mei = 1 ORDER BY tanggal DESC
    """)
    return {"items": items, "publikasi": publikasi, "berita": berita,
            "n_publikasi": len(publikasi), "n_berita": len(berita)}


def pendukung(item_id: str, live: dict[str, Any]) -> dict[str, Any] | None:
    """Data pendukung live untuk item tertentu (maks. MAX_PENDUKUNG baris), atau None."""
    if item_id in PENDUKUNG_PUBLIKASI and live["publikasi"]:
        if item_id == "led_b5_dosen_tendik":
            dosen = sorted({p["dosen"] for p in live["publikasi"]})
            return {"judul": "Dosen dengan publikasi terlacak di SINTA", "total": len(dosen),
                    "kolom": ["Dosen"], "rows": [[d] for d in dosen[:MAX_PENDUKUNG]], "tautan": None}
        return {"judul": "Publikasi dosen dari SINTA (maks. 10 terbaru per dosen)", "total": len(live["publikasi"]),
                "kolom": ["Dosen", "Judul", "Tahun", "Sumber"],
                "rows": [[p["dosen"], p["judul"], str(p["tahun"] or ""), p["sumber"] or ""]
                         for p in live["publikasi"][:MAX_PENDUKUNG]],
                "tautan": [p["link"] for p in live["publikasi"][:MAX_PENDUKUNG]]}
    if item_id in PENDUKUNG_BERITA and live["berita"]:
        return {"judul": "Berita dcse.fmipa.ugm.ac.id yang relevan dengan prodi", "total": len(live["berita"]),
                "kolom": ["Judul", "Tanggal"],
                "rows": [[b["judul"], str(b["tanggal"] or "")[:10]] for b in live["berita"][:MAX_PENDUKUNG]],
                "tautan": [b["url"] for b in live["berita"][:MAX_PENDUKUNG]]}
    return None


def ringkasan(item_ids: list[str], terisi_ids: set[str], live_ids: set[str]) -> dict[str, Any]:
    """Kelengkapan per kategori peta. Item lengkap = ada isian tim ATAU data live."""
    def hitung(k: str) -> dict[str, int]:
        ids = [i for i in item_ids if kategori(i) == k]
        return {"total": len(ids), "lengkap": sum(1 for i in ids if i in terisi_ids or i in live_ids)}

    lengkap = sum(1 for i in item_ids if i in terisi_ids or i in live_ids)
    total = len(item_ids)
    return {
        "total": total,
        "lengkap": lengkap,
        "persen": round(100 * lengkap / total) if total else 0,
        "terisi_manual": sum(1 for i in item_ids if i in terisi_ids),
        "tersedia": hitung("tersedia"),
        "akses_data": hitung("akses_data"),
        "penyusunan": hitung("penyusunan"),
    }
