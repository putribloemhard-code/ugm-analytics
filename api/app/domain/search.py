from __future__ import annotations

import re
from dataclasses import dataclass, field

from app.domain.source import kepmen, keywords


PILARS = ("Lingkungan", "Ekonomi", "Sosial")
YEAR_MIN = 2000
YEAR_MAX = 2030
SDG_PATTERN = re.compile(r"\bsdgs?\s*[-:]?\s*(\d{1,2})\b")
YEAR_PATTERN = re.compile(r"\b(\d{4})\b")
ACCREDITATION_PATTERN = re.compile(r"\b(akreditasi|led|lkps)\b")


@dataclass
class SearchResult:
    query: str
    page: str = "dampak"
    pillars: list[str] = field(default_factory=list)
    topics: list[str] = field(default_factory=list)
    sdgs: list[int] = field(default_factory=list)
    years: tuple[str, str] | None = None
    matched: bool = False
    explanation: str = ""


def whole_word(word: str, text: str) -> bool:
    return re.search(rf"(?<!\w){re.escape(word)}(?!\w)", text) is not None


def parse_search(query: str) -> SearchResult:
    q = " ".join((query or "").lower().split())
    result = SearchResult(query=(query or "").strip())
    mapping = kepmen()
    all_topics = mapping.LABEL_TOPIC_ALL
    all_meta = mapping.TOPIK_KEPMEN_ALL
    all_keywords = dict(keywords().KEYWORDS)
    all_keywords.update({key: value["keywords"] for key, value in mapping.TEMA_KEPMEN_LENGKAP.items()})

    if ACCREDITATION_PATTERN.search(q):
        result.page = "akreditasi"
        result.matched = True
        result.explanation = f'Hasil pencarian "{result.query}" diarahkan ke Akreditasi.'
        return result

    result.sdgs = sorted({int(match) for match in SDG_PATTERN.findall(q) if 1 <= int(match) <= 17})
    result.pillars = [pillar for pillar in PILARS if whole_word(pillar.lower(), q)]

    for topic_id, label in all_topics.items():
        if whole_word(label.lower(), q) or any(whole_word(word.lower(), q) for word in all_keywords.get(topic_id, [])):
            result.topics.append(topic_id)
    for topic_id in result.topics:
        pillar = all_meta[topic_id]["dampak"]
        if pillar not in result.pillars:
            result.pillars.append(pillar)
    result.pillars = [pillar for pillar in PILARS if pillar in result.pillars]

    years = sorted({year for year in YEAR_PATTERN.findall(q) if YEAR_MIN <= int(year) <= YEAR_MAX})
    if years:
        result.years = (years[0], years[-1])

    result.matched = bool(result.sdgs or result.pillars or result.topics or result.years)
    if result.sdgs and (result.pillars or result.topics):
        result.page = "dampak-sdgs"
    elif result.sdgs:
        result.page = "sdgs"
    else:
        result.page = "dampak"

    parts = []
    if result.pillars:
        parts.append("dampak " + ", ".join(result.pillars))
    if result.topics:
        parts.append("tema " + ", ".join(all_topics[topic] for topic in result.topics))
    if result.sdgs:
        parts.append("SDG " + ", ".join(str(sdg) for sdg in result.sdgs))
    if result.years:
        parts.append(f"tahun {result.years[0]}" if result.years[0] == result.years[1] else f"tahun {result.years[0]}–{result.years[1]}")
    if not parts:
        result.explanation = (
            f'Tidak ditemukan kata kunci spesifik pada "{result.query}". '
            "Menampilkan analisis dampak secara umum."
        )
    else:
        result.explanation = f'Hasil pencarian "{result.query}" menampilkan ' + ", ".join(parts) + "."
        if result.sdgs and result.page == "dampak-sdgs":
            result.explanation += " Filter SDG langsung tersedia di halaman SDGs."
    return result
