"""Uji tag tema Kepmen manual (services/tema_manual.py) dengan SQLite sementara + frame kecil."""
from __future__ import annotations

import pytest
from sqlalchemy import create_engine, text
from sqlalchemy.pool import StaticPool

from app.domain.models import FilterParams
from app.domain.source import kepmen
from app.services.story import build_story
from app.services.tema_manual import TagError, batalkan, ensure_schema, tandai, tanpa_tema
from test_story import make_frames

EMAIL = "uji@ugm.ac.id"


@pytest.fixture()
def engine():
    eng = create_engine("sqlite+pysqlite:///:memory:", poolclass=StaticPool, connect_args={"check_same_thread": False})
    ensure_schema(eng)
    ensure_schema(eng)   # idempoten
    return eng


def test_tanpa_tema_halaman_filter_dan_cari():
    fr = make_frames()
    semua = tanpa_tema(fr, page_size=50)
    assert [r["url"] for r in semua["rows"]] == ["u6"]  # u1-u5 bertema di fixture
    assert tanpa_tema(fr, year_to="2024")["total"] == 0
    assert tanpa_tema(fr, q="biasa")["total"] == 1 and tanpa_tema(fr, q="tidak ada")["total"] == 0
    with pytest.raises(TagError):
        tanpa_tema(fr, page_size=500)


def test_tandai_masuk_db_frame_dan_angka_dampak_lalu_batalkan(engine):
    fr = make_frames()
    total_awal = build_story(fr, FilterParams(), "impact")["executive"]["metrics"][0]["value"]
    hasil = tandai(engine, fr, "u6", ["pengabdian_masyarakat", "energi", "energi"], EMAIL)
    assert hasil["topiks"] == ["energi", "pengabdian_masyarakat"]
    with engine.connect() as c:
        rows = c.execute(text("SELECT url, topik, dampak, sdg, oleh FROM berita_tema_manual ORDER BY topik")).all()
    meta = kepmen().TOPIK_KEPMEN_ALL
    assert [(r[0], r[1], r[2], r[4]) for r in rows] == [
        ("u6", "energi", meta["energi"]["dampak"], EMAIL),
        ("u6", "pengabdian_masyarakat", meta["pengabdian_masyarakat"]["dampak"], EMAIL)]
    # Klaster SDG tema ikut ke bs (mode Dampak x SDGs) dan berita langsung dihitung.
    sdg_resmi = {int(s) for t in ("energi", "pengabdian_masyarakat") for s in meta[t]["sdg"]}
    assert set(fr.bs.loc[fr.bs["url"] == "u6", "sdg"]) == sdg_resmi
    assert build_story(fr, FilterParams(), "impact")["executive"]["metrics"][0]["value"] == total_awal + 1
    assert tanpa_tema(fr)["total"] == 0
    with pytest.raises(TagError):                                   # sudah bertema, tidak boleh dobel
        tandai(engine, fr, "u6", ["energi"], EMAIL)

    batalkan(engine, fr, "u6")
    assert "u6" not in set(fr.bk["url"]) and "u6" not in set(fr.bs["url"])
    assert tanpa_tema(fr)["total"] == 1
    with engine.connect() as c:
        assert c.execute(text("SELECT COUNT(*) FROM berita_tema_manual")).scalar() == 0


def test_validasi_tag(engine):
    fr = make_frames()
    for topiks in ([], None, "energi", ["bukan_tema"]):
        with pytest.raises(TagError):
            tandai(engine, fr, "u6", topiks, EMAIL)
    with pytest.raises(TagError):
        tandai(engine, fr, "https://contoh.com/tidak-ada", ["energi"], EMAIL)
    with pytest.raises(TagError):                                   # tema otomatis dari pipeline
        tandai(engine, fr, "u1", ["energi"], EMAIL)
    with pytest.raises(TagError):                                   # tema pipeline tak bisa dibatalkan
        batalkan(engine, fr, "u1")


def test_endpoint_tag_butuh_login_dampak(monkeypatch):
    from fastapi.testclient import TestClient

    from app.api.v1 import analytics
    from app.main import app

    class Fake:
        engine = object()

    sebelumnya = dict(app.dependency_overrides)
    app.dependency_overrides[analytics.service] = lambda: Fake()
    try:
        client = TestClient(app)
        monkeypatch.setattr(analytics, "_frames", lambda api: make_frames())
        r = client.get("/api/v1/analytics/tema-manual/untagged", params={"page_size": 5})
        assert r.status_code == 200 and r.json()["total"] == 1
        assert client.get("/api/v1/analytics/tema-manual/untagged", params={"page_size": 99}).status_code == 422
        assert client.post("/api/v1/analytics/tema-manual", json={"url": "u6", "topiks": ["energi"]}).status_code == 401
        assert client.post("/api/v1/analytics/tema-manual/delete", json={"url": "u6"}).status_code == 401
    finally:
        app.dependency_overrides.clear()
        app.dependency_overrides.update(sebelumnya)
