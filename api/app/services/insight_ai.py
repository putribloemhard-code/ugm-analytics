"""Narasi AI di halaman Dampak: ringkasan eksekutif (otomatis) dan insight per bab (tombol).

Angka dihitung ulang di server dari filter yang sama dengan halaman (build_story),
diringkas jadi teks, lalu LLM HANYA diminta merangkai angka itu jadi narasi -- bukan
menghitung atau mengarang angka sendiri (prinsip yang sama dengan
berita-dampak/scripts/generate_narasi_llm.py). Hasil di-cache di memori per
(jenis, mode, filter, data_as_of) supaya kunjungan/klik ulang tidak memanggil LLM lagi.
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

_ATURAN = (
    "ATURAN KETAT: pakai hanya angka yang ada di data, jangan mengubah, membulatkan, atau mengarang angka; "
    "jangan menambah klaim yang tidak didukung data; angka berita adalah hasil pencocokan kata kunci "
    "(batas bawah), jadi jangan menyebutnya sebagai capaian final. "
    "Tulis teks biasa tanpa markdown, heading, atau bullet; pisahkan paragraf dengan satu baris kosong."
)
PROMPT_BAB = (
    "Kamu analis untuk laporan dampak sosial, ekonomi, dan lingkungan sebuah universitas. "
    "Tulis insight Bahasa Indonesia yang profesional dari data satu bab laporan yang diberikan. " + _ATURAN +
    " Format: 2 paragraf pendek. Paragraf 1 = gambaran umum dan tema yang menonjol; paragraf 2 = tren "
    "tahunan, tema yang masih lemah, dan satu saran tindak lanjut."
)
PROMPT_RINGKASAN = (
    "Kamu analis untuk laporan dampak sosial, ekonomi, dan lingkungan sebuah universitas. "
    "Tulis ringkasan eksekutif Bahasa Indonesia yang profesional dari data keseluruhan yang diberikan, "
    "untuk pimpinan yang hanya sempat membaca bagian ini. " + _ATURAN +
    " Format: 2-3 paragraf pendek. Paragraf 1 = skala keseluruhan dan pembagian antar dampak (termasuk "
    "berita yang masuk lebih dari satu dampak); paragraf 2 = dampak/tema yang menonjol dan perubahannya; "
    "paragraf 3 (bila datanya ada) = hal yang masih lemah atau perlu diperhatikan."
)

_cache: OrderedDict[str, str] = OrderedDict()
_cache_lock = threading.Lock()


class InsightError(Exception):
    """Galat yang pesannya aman ditampilkan ke pengguna."""


def tersedia() -> bool:
    return bool(os.environ.get("OPENAI_API_KEY"))


def _baris_filter(filters: dict[str, Any]) -> list[str]:
    baris = [f"Rentang tahun filter: {filters.get('year_from')}–{filters.get('year_to')}"]
    if filters.get("units"):
        baris.append(f"Dibatasi fakultas/unit kerja: {', '.join(filters['units'])}")
    if filters.get("sdgs"):
        baris.append(f"Dibatasi SDG: {', '.join(str(s) for s in filters['sdgs'])}")
    return baris


def _metrik(metrics: list[dict[str, Any]]) -> list[str]:
    return [f"{m['label']}: {m['value']}" + (f" ({m['note']})" if m.get("note") else "") for m in metrics]


def ringkas_bab(chapter: dict[str, Any], filters: dict[str, Any]) -> str:
    """Ringkasan angka satu bab sebagai teks untuk prompt (semua angka berasal dari build_story)."""
    baris = [f"Bab: {chapter['title']}", *_baris_filter(filters), *_metrik(chapter.get("metrics", []))]
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


def ringkas_eksekutif(story: dict[str, Any]) -> str:
    """Ringkasan angka seluruh halaman (metrik eksekutif, pembagian, per dampak, per bab) untuk prompt."""
    executive = story.get("executive", {})
    baris = [f"Mode analisis: {story.get('mode')}", *_baris_filter(story.get("filters", {})),
             *_metrik(executive.get("metrics", []))]
    pembagian = executive.get("pembagian")
    if pembagian:
        baris.append(f"Pembagian berita dampak (total {pembagian['total']}, irisan tidak tumpang tindih):")
        baris += [f"- {i['label']}: {i['jumlah']} ({i.get('persen', 0)}%)" for i in pembagian["irisan"]]
        baris.append("Jumlah berita per dampak (satu berita bisa masuk beberapa dampak):")
        baris += [f"- {p['pilar']}: {p['jumlah']} ({p.get('persen', 0)}%)" for p in pembagian["per_pilar"]]
    for row in story.get("overview", []):
        if row.get("top_topic"):
            baris.append(f"Dampak {row['pillar']}: tema terbanyak {row['top_topic']} ({row['top_topic_count']} berita)")
    for chart in story.get("cross", {}).get("charts", []):
        if chart.get("insight"):
            baris.append(f"{chart['title']}: {chart['insight']}")
    for chapter in story.get("chapters", []):
        baris.append(f"{chapter['title']}: " + "; ".join(_metrik(chapter.get("metrics", []))))
        for chart in chapter.get("charts", []):
            if chart.get("insight"):
                baris.append(f"    {chart['title']}: {chart['insight']}")
    peta = story.get("sdg_peta") or {}
    tiles = sorted(peta.get("tiles", []), key=lambda t: t["jumlah"], reverse=True)
    if tiles:
        baris.append("SDG terbanyak: " + "; ".join(f"SDG {t['sdg']} {t['nama']} ({t['jumlah']} berita)" for t in tiles[:5]))
        baris.append("SDG paling sedikit: " + "; ".join(f"SDG {t['sdg']} {t['nama']} ({t['jumlah']} berita)" for t in tiles[-3:]))
    if executive.get("narrative"):
        baris.append(f"Ringkasan template (rujukan fakta, jangan disalin): {executive['narrative']}")
    return "\n".join(baris)


def _client():
    from openai import OpenAI

    return OpenAI(api_key=os.environ["OPENAI_API_KEY"], base_url=os.environ.get("OPENAI_BASE_URL") or None,
                  timeout=_TIMEOUT_DETIK, max_retries=1)


def _rangkai(kunci: str, system_prompt: str, data: str, client: Any, label: str) -> tuple[str, bool]:
    """Teks LLM untuk `data` (dari cache bila ada); balikin (teks, dari_cache)."""
    with _cache_lock:
        if kunci in _cache:
            _cache.move_to_end(kunci)
            return _cache[kunci], True
    if client is None and not tersedia():
        raise InsightError("Fitur AI belum dikonfigurasi (OPENAI_API_KEY kosong).")
    try:
        resp = (client or _client()).chat.completions.create(
            model=MODEL,
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": f"Data (angka wajib dipakai apa adanya):\n{data}"},
            ],
        )
        teks = (resp.choices[0].message.content or "").strip()
    except Exception as exc:  # noqa: BLE001 -- galat jaringan/kuota apa pun = pesan ramah
        logging.getLogger(__name__).exception("narasi AI %s gagal", label)
        raise InsightError("Layanan AI sedang tidak bisa dihubungi. Coba lagi beberapa saat lagi.") from exc
    if not teks:
        raise InsightError("AI tidak mengembalikan teks. Coba lagi.")
    with _cache_lock:
        _cache[kunci] = teks
        while len(_cache) > _CACHE_MAKS:
            _cache.popitem(last=False)
    return teks, False


def _kunci(jenis: str, story: dict[str, Any]) -> str:
    return json.dumps([jenis, story.get("mode"), story.get("filters"), story.get("data_as_of")], sort_keys=True)


def generate_insight(story: dict[str, Any], pillar: str, client: Any = None) -> dict[str, Any]:
    chapter = next((c for c in story.get("chapters", []) if c["pillar"] == pillar), None)
    if chapter is None:
        raise InsightError(f"Bab dampak {pillar} tidak ada pada filter ini.")
    if not chapter.get("total"):
        raise InsightError(f"Belum ada berita dampak {pillar} pada filter ini, jadi belum ada yang bisa dianalisis.")
    teks, cached = _rangkai(_kunci(f"bab:{pillar}", story), PROMPT_BAB,
                            ringkas_bab(chapter, story.get("filters", {})), client, f"bab {pillar}")
    return {"pillar": pillar, "insight": teks, "cached": cached}


def generate_ringkasan(story: dict[str, Any], client: Any = None) -> dict[str, Any]:
    if not story.get("executive", {}).get("metrics"):
        raise InsightError("Belum ada data untuk filter ini, jadi belum ada yang bisa diringkas.")
    teks, cached = _rangkai(_kunci("ringkasan", story), PROMPT_RINGKASAN, ringkas_eksekutif(story), client, "ringkasan")
    return {"narrative": teks, "cached": cached}
