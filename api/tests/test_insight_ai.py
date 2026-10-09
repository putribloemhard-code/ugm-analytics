"""Insight AI per bab: prompt memuat angka bab, cache per filter, galat ramah (klien LLM tiruan)."""
from __future__ import annotations

from types import SimpleNamespace

import pytest

from app.domain.models import FilterParams
from app.services import insight_ai
from app.services.insight_ai import InsightError, generate_insight, generate_ringkasan, ringkas_bab, ringkas_eksekutif
from app.services.story import build_story
from tests.test_story import make_frames


class KlienTiruan:
    def __init__(self, jawaban: str = "Insight uji.", galat: Exception | None = None):
        self.panggilan: list[list[dict]] = []
        self.jawaban, self.galat = jawaban, galat
        self.chat = SimpleNamespace(completions=SimpleNamespace(create=self._create))

    def _create(self, model: str, messages: list[dict]):
        self.panggilan.append(messages)
        if self.galat:
            raise self.galat
        return SimpleNamespace(choices=[SimpleNamespace(message=SimpleNamespace(content=self.jawaban))])


@pytest.fixture(autouse=True)
def cache_kosong():
    insight_ai._cache.clear()
    yield
    insight_ai._cache.clear()


def test_ringkas_bab_memuat_metrik_dan_tema():
    story = build_story(make_frames(), FilterParams(), "impact")
    bab = next(c for c in story["chapters"] if c["pillar"] == "Sosial")
    teks = ringkas_bab(bab, story["filters"])
    assert bab["title"] in teks
    assert "Berita dampak: 2" in teks
    assert "Pendidikan Inklusif" in teks


def test_generate_insight_memakai_cache_per_filter():
    story = build_story(make_frames(), FilterParams(), "impact")
    klien = KlienTiruan("Dua paragraf insight.")
    pertama = generate_insight(story, "Sosial", client=klien)
    kedua = generate_insight(story, "Sosial", client=klien)
    assert pertama == {"pillar": "Sosial", "insight": "Dua paragraf insight.", "cached": False}
    assert kedua["cached"] is True
    assert len(klien.panggilan) == 1

    lain = build_story(make_frames(), FilterParams(year_from="2025", year_to="2025"), "impact")
    assert generate_insight(lain, "Sosial", client=klien)["cached"] is False
    assert len(klien.panggilan) == 2


def test_generate_insight_galat_llm_jadi_pesan_ramah():
    story = build_story(make_frames(), FilterParams(), "impact")
    with pytest.raises(InsightError, match="tidak bisa dihubungi"):
        generate_insight(story, "Sosial", client=KlienTiruan(galat=TimeoutError("habis")))
    assert not insight_ai._cache


def test_generate_insight_bab_tanpa_berita_tidak_memanggil_llm():
    story = build_story(make_frames(), FilterParams(year_from="2023", year_to="2023"), "impact")
    klien = KlienTiruan()
    with pytest.raises(InsightError):
        generate_insight(story, "Sosial", client=klien)
    assert not klien.panggilan


def test_ringkas_eksekutif_memuat_pembagian_dan_bab():
    story = build_story(make_frames(), FilterParams(), "impact")
    teks = ringkas_eksekutif(story)
    assert "Total berita dampak" in teks
    assert "Pembagian berita dampak" in teks
    assert all(c["title"] in teks for c in story["chapters"])


def test_generate_ringkasan_cache_terpisah_dari_insight_bab():
    story = build_story(make_frames(), FilterParams(), "impact")
    klien = KlienTiruan("Ringkasan uji.")
    assert generate_ringkasan(story, client=klien) == {"narrative": "Ringkasan uji.", "cached": False}
    assert generate_ringkasan(story, client=klien)["cached"] is True
    assert generate_insight(story, "Sosial", client=klien)["cached"] is False
    assert len(klien.panggilan) == 2
