"""Uji log aktivitas (services/aktivitas.py), draf suntingan Laporan Dampak (services/laporan_draf.py),
dan email admin (services/notifikasi.py)."""
from __future__ import annotations


import pytest
from sqlalchemy import create_engine, text
from sqlalchemy.pool import StaticPool

from app.services import aktivitas, laporan_draf, notifikasi


@pytest.fixture()
def engine():
    eng = create_engine("sqlite+pysqlite:///:memory:", poolclass=StaticPool, connect_args={"check_same_thread": False})
    aktivitas.ensure_schema(eng)
    aktivitas.ensure_schema(eng)  # idempoten
    laporan_draf.ensure_schema(eng)
    laporan_draf.ensure_schema(eng)
    with eng.begin() as conn:
        conn.execute(text("CREATE TABLE akreditasi_users (id INTEGER PRIMARY KEY, email VARCHAR(254), is_admin BOOLEAN, is_blocked BOOLEAN)"))
        conn.execute(text("INSERT INTO akreditasi_users VALUES (1, 'admin@ugm.ac.id', 1, 0), (2, 'staf@ugm.ac.id', 0, 0), "
                          "(3, 'lama@ugm.ac.id', 1, 1)"))
    return eng


STAF = {"email": "staf@ugm.ac.id", "nama": "Staf Prodi"}


def test_aktivitas_per_laporan_dan_portal(engine):
    aktivitas.catat(engine, "akreditasi", STAF, "ubah_isian", "Mengubah isian: Identitas", laporan_id=5)
    aktivitas.catat(engine, "akreditasi", STAF, "unggah", "Mengunggah a.pdf", laporan_id=6)
    aktivitas.catat(engine, "dampak", {"email": "tim@ugm.ac.id"}, "tag_tema", "Menandai tema berita")
    lap5 = aktivitas.daftar(engine, "akreditasi", laporan_id=5)
    assert [a["keterangan"] for a in lap5] == ["Mengubah isian: Identitas"]
    assert lap5[0]["pelaku_nama"] == "Staf Prodi" and lap5[0]["created_at"]
    assert len(aktivitas.daftar(engine, "akreditasi")) == 2
    assert [a["aksi"] for a in aktivitas.daftar(engine, "dampak")] == ["tag_tema"]
    with pytest.raises(ValueError):
        aktivitas.daftar(engine, "lain")


def test_catat_tidak_pernah_menggagalkan_aksi():
    rusak = create_engine("sqlite+pysqlite:///:memory:")  # tabel belum ada
    aktivitas.catat(rusak, "akreditasi", STAF, "x", "y")  # tidak melempar galat


FILTER = {"mode": "impact", "year_from": "2024", "pillars": ["Sosial"]}


def test_draf_disimpan_per_akun_dan_filter(engine):
    s = {"3": {"asli": "Teks lama.", "baru": "Teks baru."}, "7": {"asli": "Sama.", "baru": "Sama."}}
    hasil = laporan_draf.simpan(engine, 14, FILTER, s)
    assert hasil["jumlah"] == 1  # paragraf yang tidak berubah tidak disimpan
    assert laporan_draf.ambil(engine, 14, {"pillars": ["Sosial"], "year_from": "2024", "mode": "impact"})["suntingan"] == {
        "3": {"asli": "Teks lama.", "baru": "Teks baru."}}
    assert laporan_draf.ambil(engine, 15, FILTER)["suntingan"] == {}  # akun lain
    assert laporan_draf.ambil(engine, 14, {**FILTER, "mode": "sdgs"})["suntingan"] == {}  # filter lain
    laporan_draf.simpan(engine, 14, FILTER, {})  # kosong = hapus draf
    assert laporan_draf.ambil(engine, 14, FILTER) == {"suntingan": {}, "updated_at": None}


@pytest.mark.parametrize("buruk", [[], {"x": {"asli": "a", "baru": "b"}}, {"1": "teks"}, {"1": {"asli": "a", "baru": "b" * 20001}}])
def test_draf_menolak_format_salah(engine, buruk):
    with pytest.raises(laporan_draf.DrafError):
        laporan_draf.simpan(engine, 14, FILTER, buruk)


def test_email_admin_hanya_ke_admin_aktif(engine, monkeypatch):
    terkirim: list[str] = []
    monkeypatch.setattr(notifikasi.mailer, "terkonfigurasi", lambda: True)
    monkeypatch.setattr(notifikasi.mailer, "kirim", lambda ke, subjek, isi: terkirim.append(ke))

    class Langsung:  # jalankan "thread" langsung supaya bisa diperiksa
        def __init__(self, target, args, daemon):
            self.target, self.args = target, args

        def start(self):
            self.target(*self.args)

    monkeypatch.setattr(notifikasi.threading, "Thread", Langsung)
    assert notifikasi.kabari_admin(engine, "akreditasi", "Subjek", "Isi") == 1
    assert terkirim == ["admin@ugm.ac.id"]
    assert notifikasi.email_uji("akreditasi", "admin@ugm.ac.id")["terkirim"] is True


def test_tanpa_smtp_tidak_mengirim(engine, monkeypatch):
    monkeypatch.setattr(notifikasi.mailer, "terkonfigurasi", lambda: False)
    assert notifikasi.kabari_admin(engine, "akreditasi", "S", "I") == 0
    hasil = notifikasi.email_uji("dampak", "a@ugm.ac.id")
    assert hasil["terkirim"] is False and "smtp.env" in hasil["message"]


def test_email_uji_melaporkan_galat_smtp(monkeypatch):
    monkeypatch.setattr(notifikasi.mailer, "terkonfigurasi", lambda: True)

    def gagal(*a):
        raise ConnectionRefusedError("x")
    monkeypatch.setattr(notifikasi.mailer, "kirim", gagal)
    hasil = notifikasi.email_uji("akreditasi", "a@ugm.ac.id")
    assert hasil["terkirim"] is False and "ConnectionRefusedError" in hasil["message"]


def test_endpoint_draf_butuh_login_dan_memakai_filter(engine, monkeypatch):
    from fastapi.testclient import TestClient

    from app.api.v1 import analytics
    from app.main import app

    class Fake:
        pass

    Fake.engine = engine
    sebelumnya = dict(app.dependency_overrides)
    app.dependency_overrides[analytics.service] = lambda: Fake()
    try:
        client = TestClient(app)
        # Tanpa login Analisis Dampak -> 401
        assert client.post("/api/v1/analytics/reports/draf/ambil", json={"filter": FILTER}).status_code == 401
        monkeypatch.setattr(analytics, "_dampak_auth_user", lambda request, api: {"id": 14, "email": "tim@ugm.ac.id", "is_admin": True})
        s = {"2": {"asli": "A.", "baru": "B."}}
        r = client.post("/api/v1/analytics/reports/draf", json={"filter": FILTER, "suntingan": s})
        assert r.status_code == 200 and r.json()["jumlah"] == 1
        assert client.post("/api/v1/analytics/reports/draf/ambil", json={"filter": FILTER}).json()["suntingan"] == s
        assert client.post("/api/v1/analytics/reports/draf", json={"filter": {"mode": "salah"}, "suntingan": s}).status_code == 422
        assert client.post("/api/v1/analytics/reports/draf", json={"filter": FILTER, "suntingan": [1]}).status_code == 400
        assert client.get("/api/v1/analytics/dampak/admin/aktivitas").json() == {"aktivitas": []}
    finally:
        app.dependency_overrides.clear()
        app.dependency_overrides.update(sebelumnya)
