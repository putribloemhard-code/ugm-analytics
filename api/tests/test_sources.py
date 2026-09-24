"""Uji bagian "Sumber" (services/sources.py): ringkasan asal data + daftar berita berdampak."""
from __future__ import annotations

import pytest
from fastapi.testclient import TestClient

from app.services.sources import berita_berdampak, ringkasan_sumber
from test_story import make_frames, make_matkul


def frames(dengan_matkul: bool = True):
    fr = make_frames()
    fr.matkul = make_matkul() if dengan_matkul else None
    return fr


def test_ringkasan_berita_dihitung_dari_data():
    fr = frames()
    r = ringkasan_sumber(fr)["berita"]
    assert r["situs"] == "ugm.ac.id"
    assert r["diambil"] == len(fr.berita)
    assert r["berdampak"] == fr.bk["url"].nunique()
    assert r["berdampak"] <= r["diambil"]
    assert r["tahun_awal"] <= r["tahun_akhir"]
    assert [p["pilar"] for p in r["per_pilar"]] == ["Sosial", "Ekonomi", "Lingkungan"]
    assert sum(r["bahasa"].values()) == r["diambil"]


def test_ringkasan_mata_kuliah_dan_sumber_internal_jujur():
    s = ringkasan_sumber(frames())
    mk = s["mata_kuliah"]
    assert mk["tersedia"] is True and mk["baris"] == 8   # 8 baris uji
    assert mk["indikator_resmi"] == 3 and mk["berdampak"] == 5
    assert mk["berdampak"] <= mk["mk_unik"]
    assert {p["pilar"]: p["jumlah"] for p in mk["per_pilar"]}["Lingkungan"] == 3
    assert s["internal"][0]["status"] == "Belum ada akses"
    assert ringkasan_sumber(frames(dengan_matkul=False))["mata_kuliah"] == {"tersedia": False}


def test_berita_berdampak_satu_baris_per_berita_dengan_tautan():
    fr = frames()
    fr.berita["url"] = "https://ugm.ac.id/id/berita/" + fr.berita["url"]
    fr.bk["url"] = "https://ugm.ac.id/id/berita/" + fr.bk["url"]
    hasil = berita_berdampak(fr, page_size=50)
    urls = [r["tautan"] for r in hasil["rows"]]
    assert hasil["total"] == fr.bk["url"].nunique() == len(urls) == len(set(urls))
    assert all(u.startswith("https://ugm.ac.id/") for u in urls)
    assert all(r["tema"] and r["pilar"] for r in hasil["rows"])
    tanggal = [r["tanggal"] for r in hasil["rows"]]
    assert tanggal == sorted(tanggal, reverse=True)


def test_berita_berdampak_filter_pilar_cari_dan_halaman():
    fr = frames()
    ling = berita_berdampak(fr, pilar="Lingkungan", page_size=50)
    assert ling["total"] == fr.bk.loc[fr.bk["dampak"] == "Lingkungan", "url"].nunique()
    assert all("Lingkungan" in r["pilar"] for r in ling["rows"])
    judul = fr.berita.loc[fr.berita["url"].isin(fr.bk["url"]), "judul"].iloc[0]
    kata = judul.split()[0]
    cari = berita_berdampak(fr, q=kata.upper(), page_size=50)   # tidak peka huruf besar
    assert cari["total"] >= 1 and all(kata.lower() in r["judul"].lower() for r in cari["rows"])
    satu = berita_berdampak(fr, page=2, page_size=1)
    assert len(satu["rows"]) == 1 and satu["page"] == 2 and satu["total"] >= 2
    with pytest.raises(ValueError):
        berita_berdampak(fr, pilar="Budaya")
    with pytest.raises(ValueError):
        berita_berdampak(fr, page_size=500)


def test_tautan_non_http_tidak_dikirim():
    fr = frames()
    url = fr.bk["url"].iloc[0]
    fr.berita.loc[fr.berita["url"] == url, "url"] = "javascript:alert(1)"
    fr.bk.loc[fr.bk["url"] == url, "url"] = "javascript:alert(1)"
    rows = berita_berdampak(fr, page_size=50)["rows"]
    assert all(r["tautan"] is None or r["tautan"].startswith("http") for r in rows)


def test_endpoint_sumber_memakai_frame_cache(monkeypatch):
    from app.api.v1.analytics import service
    from app.main import app
    from app.services import story

    class Fake:
        engine = object()

    fr = frames()
    monkeypatch.setattr(story.StoryService, "frames", lambda self: fr)
    sebelumnya = dict(app.dependency_overrides)
    app.dependency_overrides[service] = lambda: Fake()
    try:
        client = TestClient(app)
        r = client.get("/api/v1/analytics/sources")
        assert r.status_code == 200 and r.json()["berita"]["diambil"] == len(fr.berita)
        n = client.get("/api/v1/analytics/sources/news", params={"page_size": 5, "pilar": "Sosial"})
        assert n.status_code == 200 and n.json()["page_size"] == 5
        assert client.get("/api/v1/analytics/sources/news", params={"pilar": "Budaya"}).status_code == 422
        assert client.get("/api/v1/analytics/sources/news", params={"page_size": 99}).status_code == 422
    finally:
        app.dependency_overrides.clear()
        app.dependency_overrides.update(sebelumnya)
