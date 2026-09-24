"""Uji tag SDG manual (services/sdg_manual.py) dengan SQLite sementara + frame kecil."""
from __future__ import annotations

import pytest
from sqlalchemy import create_engine, text
from sqlalchemy.pool import StaticPool

from app.services.sdg_manual import TagError, batalkan, belum_bertanda, ensure_schema, tandai
from test_story import make_frames


@pytest.fixture()
def engine():
    eng = create_engine("sqlite+pysqlite:///:memory:", poolclass=StaticPool, connect_args={"check_same_thread": False})
    ensure_schema(eng)
    ensure_schema(eng)   # idempoten
    return eng


def test_belum_bertanda_halaman_dan_cari():
    fr = make_frames()
    semua = belum_bertanda(fr, page_size=50)
    tagged = set(fr.ss["url"])
    assert semua["total"] == fr.sitemap["url"].nunique() - len(tagged & set(fr.sitemap["url"]))
    assert all(r["url"] not in tagged for r in semua["rows"])
    tanggal = [r["tanggal"] for r in semua["rows"]]
    assert tanggal == sorted(tanggal, reverse=True)
    satu = belum_bertanda(fr, page=2, page_size=1)
    assert len(satu["rows"]) == 1 and satu["total"] == semua["total"]
    with pytest.raises(TagError):
        belum_bertanda(fr, page_size=500)


def test_tandai_simpan_ke_db_dan_perbarui_frame_lalu_batalkan(engine):
    fr = make_frames()
    url = belum_bertanda(fr, page_size=1)["rows"][0]["url"]
    sebelum = belum_bertanda(fr, page_size=50)["total"]
    hasil = tandai(engine, fr, url, [7, "13", 7], "uji@ugm.ac.id")
    assert hasil["sdgs"] == [7, 13]
    with engine.connect() as c:
        rows = c.execute(text("SELECT url, sdg, oleh FROM berita_sdg_manual ORDER BY sdg")).all()
    assert [tuple(r) for r in rows] == [(url, 7, "uji@ugm.ac.id"), (url, 13, "uji@ugm.ac.id")]
    assert set(fr.ss.loc[fr.ss["url"] == url, "sdg"]) == {7, 13}           # cache langsung ikut
    assert belum_bertanda(fr, page_size=50)["total"] == sebelum - 1
    with pytest.raises(TagError):                                          # tidak boleh dobel
        tandai(engine, fr, url, [1], "uji@ugm.ac.id")

    batalkan(engine, fr, url)
    assert url not in set(fr.ss["url"])
    assert belum_bertanda(fr, page_size=50)["total"] == sebelum
    with engine.connect() as c:
        assert c.execute(text("SELECT COUNT(*) FROM berita_sdg_manual")).scalar() == 0


def test_validasi_tag(engine):
    fr = make_frames()
    url = belum_bertanda(fr, page_size=1)["rows"][0]["url"]
    for sdgs in ([], [0], [18], ["x"], None):
        with pytest.raises(TagError):
            tandai(engine, fr, url, sdgs, "uji@ugm.ac.id")
    with pytest.raises(TagError):
        tandai(engine, fr, "https://contoh.com/bukan-sitemap", [1], "uji@ugm.ac.id")
    sudah = fr.ss["url"].iloc[0]
    with pytest.raises(TagError):                                          # sudah bertanda otomatis
        tandai(engine, fr, sudah, [1], "uji@ugm.ac.id")
    with pytest.raises(TagError):                                          # tag otomatis tak bisa dibatalkan
        batalkan(engine, fr, sudah)


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
        r = client.get("/api/v1/analytics/sdg-manual/untagged", params={"page_size": 5})
        assert r.status_code == 200 and len(r.json()["rows"]) <= 5
        assert client.post("/api/v1/analytics/sdg-manual", json={"url": "x", "sdgs": [1]}).status_code == 401
        assert client.post("/api/v1/analytics/sdg-manual/delete", json={"url": "x"}).status_code == 401
    finally:
        app.dependency_overrides.clear()
        app.dependency_overrides.update(sebelumnya)
