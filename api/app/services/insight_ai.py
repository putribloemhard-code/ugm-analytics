"""Tombol "Generate insight" per bab Laporan Dampak (Sosial/Ekonomi/Lingkungan).

Angka bab dihitung ulang di server dari filter yang sama dengan halaman (build_story),
diringkas jadi teks, lalu LLM HANYA diminta merangkai angka itu jadi narasi -- bukan
menghitung atau mengarang angka sendiri (prinsip yang sama dengan
berita-dampak/scripts/generate_narasi_llm.py). Hasil di-cache di memori per
(mode, filter, bab, data_as_of) supaya klik ulang tidak memanggil LLM lagi.
"""
from __future__ import annotations

import json
import logging
import os
import threading
from collections import OrderedDict
from typing import Any

MODEL = "cx/gpt-5.6-luna"
_TIMEOUT_DETIK = 90  # gateway memutus panggilan di 120 detik (lihat akreditasi/scripts/ekstraksi_akreditasi.py)
_CACHE_MAKS = 200

SYSTEM_PROMPT = (
    "Kamu analis untuk laporan dampak sosial, ekonomi, dan lingkungan sebuah universitas. "
    "Tulis insight Bahasa Indonesia yang profesional dari data satu bab laporan yang diberikan. "
    "ATURAN KETAT: pakai hanya angka yang ada di data, jangan mengubah, membulatkan, atau mengarang angka; "
    "jangan menambah klaim yang tidak didukung data; angka berita adalah hasil pencocokan kata kunci "
    "(batas bawah), jadi jangan menyebutnya sebagai capaian final. "
    "Format: 2 paragraf pendek teks biasa tanpa markdown, heading, atau bullet. Paragraf 1 = gambaran "
    "umum dan tema yang menonjol; paragraf 2 = tren tahunan, tema yang masih lemah, dan satu saran tindak lanjut."
)

_cache: OrderedDict[str, str] = OrderedDict()
_cache_lock = threading.Lock()


class InsightError(Exception):
    """Galat yang pesannya aman ditampilkan ke pengguna."""


def tersedia() -> bool:
    return bool(os.environ.get("OPENAI_API_KEY"))


def ringkas_bab(chapter: dict[str, Any], filters: dict[str, Any]) -> str:
    """Ringkasan angka satu bab sebagai teks untuk prompt (semua angka berasal dari build_story)."""
    baris = [
        f"Bab: {chapter['title']}",
        f"Rentang tahun filter: {filters.get('year_from')}–{filters.get('year_to')}",
    ]
    if filters.get("units"):
        baris.append(f"Dibatasi fakultas/unit kerja: {', '.join(filters['units'])}")
    baris += [f"{m['label']}: {m['value']}" for m in chapter.get("metrics", [])]
    for chart in chapter.get("charts", []):
        if chart.get("insight"):
            baris.append(f"{chart['title']}: {chart['insight']}")
    baris.append("Per tema:")
    for section in chapter.get("subsections", []):
        metrik = ", ".join(f"{m['label']} {m['value']}" for m in section.get("metrics", []))
        judul = " ".join(filter(None, [section.get("number"), section["label"]]))
        baris.append(f"- {judul} ({metrik})")
        for chart in section.get("charts", []):
            if chart.get("insight"):
                baris.append(f"    {chart['title']}: {chart['insight']}")
    return "\n".join(baris)


def _client():
    from openai import OpenAI

    return OpenAI(api_key=os.environ["OPENAI_API_KEY"], base_url=os.environ.get("OPENAI_BASE_URL") or None,
                  timeout=_TIMEOUT_DETIK, max_retries=1)


def generate_insight(story: dict[str, Any], pillar: str, client: Any = None) -> dict[str, Any]:
    chapter = next((c for c in story.get("chapters", []) if c["pillar"] == pillar), None)
    if chapter is None:
        raise InsightError(f"Bab dampak {pillar} tidak ada pada filter ini.")
    if not chapter.get("total"):
        raise InsightError(f"Belum ada berita dampak {pillar} pada filter ini, jadi belum ada yang bisa dianalisis.")
    if client is None and not tersedia():
        raise InsightError("Generate insight AI belum dikonfigurasi (OPENAI_API_KEY kosong).")

    kunci = json.dumps([story.get("mode"), story.get("filters"), pillar, story.get("data_as_of")], sort_keys=True)
    with _cache_lock:
        if kunci in _cache:
            _cache.move_to_end(kunci)
            return {"pillar": pillar, "insight": _cache[kunci], "cached": True}

    data = ringkas_bab(chapter, story.get("filters", {}))
    try:
        resp = (client or _client()).chat.completions.create(
            model=MODEL,
            messages=[
                {"role": "system", "content": SYSTEM_PROMPT},
                {"role": "user", "content": f"Data bab (angka wajib dipakai apa adanya):\n{data}"},
            ],
        )
        teks = (resp.choices[0].message.content or "").strip()
    except Exception as exc:  # noqa: BLE001 -- galat jaringan/kuota apa pun = pesan ramah
        logging.getLogger(__name__).exception("generate insight %s gagal", pillar)
        raise InsightError("Layanan AI sedang tidak bisa dihubungi. Coba lagi beberapa saat lagi.") from exc
    if not teks:
        raise InsightError("AI tidak mengembalikan insight. Coba lagi.")

    with _cache_lock:
        _cache[kunci] = teks
        while len(_cache) > _CACHE_MAKS:
            _cache.popitem(last=False)
    return {"pillar": pillar, "insight": teks, "cached": False}
