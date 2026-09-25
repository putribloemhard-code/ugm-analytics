"""Uji laporan per prodi + tahun, password prodi, reset lewat admin, dan migrasi data lama
(services/accreditation_laporan.py)."""
from __future__ import annotations

from datetime import datetime, timedelta

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import text

from app.services.accreditation_auth import token_hash
from app.services.accreditation_laporan import (
    AksesDitolak,
    LaporanError,
    LaporanService,
    TidakDitemukan,
    ensure_schema,
    migrasi_data_lama,
)
from test_accreditation_workspace import EMAIL, buat_laporan, engine  # noqa: F401  (fixture)

TOKEN_A, TOKEN_B = "token-staf-a", "token-staf-b"
ADMIN = {"id": 9, "email": "admin@ugm.ac.id", "nama": "Admin", "is_admin": True}


@pytest.fixture()
def svc(engine):  # noqa: F811
    with engine.begin() as conn:
        for i, tok in enumerate((TOKEN_A, TOKEN_B), start=1):
            conn.execute(text("INSERT INTO akreditasi_sessions (token_hash, user_id, created_at, expires_at) VALUES (:h, :u, :c, :e)"),
                         {"h": token_hash(tok), "u": i, "c": datetime.now(), "e": datetime.now() + timedelta(hours=12)})
        conn.execute(text("INSERT INTO akreditasi_prodi (id, fakultas_id, nama, jenjang, slug) VALUES (2, 1, 'Ilmu Komputer', 'Sarjana', 's1-ilkom')"))
    return LaporanService(engine)


def test_password_prodi_dibuat_sekali_lalu_berlaku_untuk_semua_laporan(svc):
    assert svc.daftar("mei", "LED", TOKEN_A, EMAIL)["terkunci"] is False
    with pytest.raises(AksesDitolak):  # belum membuka password -> tidak bisa membuat laporan
        svc.buat_laporan("mei", "LED", 2026, "", TOKEN_A, EMAIL)
    for pin_salah in ("12345", "abcdef12", "1234567890123", "١٢٣٤٥٦"):  # PIN hanya angka 0-9, 6-12 digit
        with pytest.raises(LaporanError):
            svc.buat_kunci("mei", pin_salah, TOKEN_A, EMAIL)
    svc.buat_kunci("mei", "123456", TOKEN_A, EMAIL)
    with pytest.raises(LaporanError):  # password prodi hanya dibuat sekali
        svc.buat_kunci("mei", "654321", TOKEN_B, "b@ugm.ac.id")
    led = svc.buat_laporan("mei", "LED", 2026, "", TOKEN_A, EMAIL)
    lkps = svc.buat_laporan("mei", "LKPS", 2026, "LKPS reakreditasi", TOKEN_A, EMAIL)
    assert led["nama"] == "LED 2026" and lkps["nama"] == "LKPS reakreditasi"
    with pytest.raises(LaporanError):  # satu laporan per prodi + dokumen + tahun
        svc.buat_laporan("mei", "LED", 2026, "", TOKEN_A, EMAIL)
    with pytest.raises(LaporanError):
        svc.buat_laporan("mei", "LED", 1990, "", TOKEN_A, EMAIL)

    # Staf lain: melihat daftar, tapi isi baru terbuka setelah memasukkan password yang sama.
    daftar = svc.daftar("mei", "LED", TOKEN_B, "b@ugm.ac.id")
    assert daftar["terkunci"] and not daftar["terbuka"] and [l["nama"] for l in daftar["laporan"]] == ["LED 2026"]
    with pytest.raises(AksesDitolak):
        svc.laporan(led["id"], TOKEN_B)
    with pytest.raises(AksesDitolak):
        svc.buka("mei", "000000", TOKEN_B, "b@ugm.ac.id")
    svc.buka("mei", "123456", TOKEN_B, "b@ugm.ac.id")
    assert svc.laporan(lkps["id"], TOKEN_B)["dokumen"] == "LKPS"
    # Password prodi MEI tidak membuka prodi lain.
    with pytest.raises(AksesDitolak):
        svc.laporan(buat_laporan(svc.engine, "LED", prodi="s1-ilkom")["id"], TOKEN_B)


def test_akses_hilang_saat_sesi_login_berakhir(svc):
    svc.buat_kunci("mei", "123456", TOKEN_A, EMAIL)
    lap = svc.buat_laporan("mei", "LED", 2026, "", TOKEN_A, EMAIL)
    with svc.engine.begin() as conn:
        conn.execute(text("DELETE FROM akreditasi_sessions WHERE token_hash = :h"), {"h": token_hash(TOKEN_A)})
    with pytest.raises(AksesDitolak):
        svc.laporan(lap["id"], TOKEN_A)
    with pytest.raises(TidakDitemukan):
        svc.laporan(9999, TOKEN_B)


def test_salah_password_lima_kali_dikunci_sementara(svc):
    svc.buat_kunci("mei", "123456", TOKEN_A, EMAIL)
    for _ in range(5):
        with pytest.raises(AksesDitolak):
            svc.buka("mei", "111111", TOKEN_B, "b@ugm.ac.id")
    with pytest.raises(AksesDitolak, match="Terlalu banyak"):
        svc.buka("mei", "123456", TOKEN_B, "b@ugm.ac.id")
    svc.buka("mei", "123456", TOKEN_A, EMAIL)  # akun lain tidak ikut terkunci


def test_reset_password_butuh_persetujuan_admin(svc):
    svc.buat_kunci("mei", "123456", TOKEN_A, EMAIL)
    staf = {"email": "b@ugm.ac.id", "nama": "Staf B"}
    svc.ajukan_reset("mei", "222222", "lupa", staf)
    svc.ajukan_reset("mei", "333333", "lupa lagi", staf)  # menggantikan pengajuan lama
    assert svc.daftar("mei", "LED", TOKEN_B, staf["email"])["reset_menunggu"] is True
    menunggu = svc.daftar_reset("menunggu")
    assert len(menunggu) == 1 and menunggu[0]["nama_pengaju"] == "Staf B" and menunggu[0]["nama_prodi"] == "Magister Elektronika dan Instrumentasi"
    with pytest.raises(AksesDitolak):  # belum disetujui -> password baru belum berlaku
        svc.buka("mei", "333333", TOKEN_B, staf["email"])
    svc.putuskan_reset(menunggu[0]["id"], True, ADMIN)
    with pytest.raises(LaporanError):
        svc.putuskan_reset(menunggu[0]["id"], False, ADMIN)
    # Password lama tidak berlaku lagi dan sesi yang terbuka dengan password lama ditutup.
    assert svc.daftar("mei", "LED", TOKEN_A, EMAIL)["terbuka"] is False
    with pytest.raises(AksesDitolak):
        svc.buka("mei", "123456", TOKEN_A, EMAIL)
    svc.buka("mei", "333333", TOKEN_B, staf["email"])
    assert svc.daftar_reset()[0]["status"] == "disetujui" and svc.daftar_reset()[0]["diputus_oleh"] == ADMIN["email"]
    with pytest.raises(LaporanError):  # prodi tanpa password: buat langsung, bukan reset
        svc.ajukan_reset("s1-ilkom", "444444", "", staf)


def test_migrasi_data_lama_ke_laporan_dan_terapkan_ekstraksi(engine):  # noqa: F811
    with engine.begin() as conn:
        conn.execute(text("INSERT INTO akreditasi_data_manual (prodi_id, item_id, baris_ke, kolom, nilai, diisi_oleh, updated_at) "
                          "VALUES ('mei', 'led_b1_sejarah', 1, 'Tanggal & SK Pendirian UPPS', 'SK lama', :e, '2026-09-19')"), {"e": EMAIL})
        conn.execute(text("INSERT INTO akreditasi_upload_file (id, prodi_id, nama_file, path_lokal, tipe_file, status, uploaded_at) "
                          "VALUES (5, 'mei', 'led.pdf', '/x/led.pdf', 'pdf', 'diekstrak', '2026-09-16')"))
        conn.execute(text("INSERT INTO akreditasi_upload_ekstraksi (upload_file_id, prodi_id, item_id, baris_ke, nama_kolom, nilai, kutipan, created_at) "
                          "VALUES (5, 'mei', 'led_b1_sejarah', 1, 'Tanggal & SK Pendirian UPPS', 'SK dari AI', 'q', '2026-09-16'), "
                          "(5, 'mei', 'led_b1_sejarah', 1, 'Tanggal Pendirian PS', '2011', 'q', '2026-09-16')"))
    migrasi_data_lama(engine)
    ensure_schema(engine)  # idempoten: tidak ada yang dipindah dua kali
    with engine.connect() as conn:
        laporan = conn.execute(text("SELECT id, prodi_id, dokumen, tahun FROM akreditasi_laporan")).all()
        assert [tuple(r)[1:] for r in laporan] == [("mei", "LED", 2026)]
        lap = laporan[0][0]
        isi = dict(conn.execute(text("SELECT kolom, nilai FROM akreditasi_data_manual WHERE laporan_id = :l"), {"l": lap}).all())
        status = dict(conn.execute(text("SELECT nilai, status_terap FROM akreditasi_upload_ekstraksi")).all())
        assert conn.execute(text("SELECT COUNT(*) FROM akreditasi_data_manual WHERE laporan_id IS NULL")).scalar() == 0
    assert isi == {"Tanggal & SK Pendirian UPPS": "SK lama", "Tanggal Pendirian PS": "2011"}
    assert status == {"SK dari AI": "tidak_menimpa", "2011": "ditambahkan"}


def test_endpoint_isi_laporan_butuh_password_prodi(engine, monkeypatch, tmp_path):  # noqa: F811
    from app.api.v1 import analytics
    from app.main import app

    class Fake:
        pass

    Fake.engine = engine
    with engine.begin() as conn:
        conn.execute(text("INSERT INTO akreditasi_sessions (token_hash, user_id, created_at, expires_at) VALUES (:h, 1, :c, :e)"),
                     {"h": token_hash(TOKEN_A), "c": datetime.now(), "e": datetime.now() + timedelta(hours=12)})
    monkeypatch.setattr(analytics, "_auth_user", lambda request, api: {"id": 1, "email": EMAIL, "nama": "Staf", "is_admin": False})
    monkeypatch.setattr(analytics.settings, "accreditation_upload_dir", str(tmp_path / "up"), raising=False)
    sebelumnya = dict(app.dependency_overrides)
    app.dependency_overrides[analytics.service] = lambda: Fake()
    try:
        client = TestClient(app)
        from app.services.accreditation_auth import COOKIE_NAME
        client.cookies.set(COOKIE_NAME, TOKEN_A)
        lap = buat_laporan(engine, "LED")
        assert client.get(f"/api/v1/analytics/accreditation/workspace?laporan_id={lap['id']}").status_code == 403
        assert client.post("/api/v1/analytics/accreditation/prodi/mei/kunci", json={"password": "123456"}).status_code == 200
        assert client.get(f"/api/v1/analytics/accreditation/workspace?laporan_id={lap['id']}").status_code == 200
        daftar = client.get("/api/v1/analytics/accreditation/laporan", params={"prodi_id": "mei", "dokumen": "LED"}).json()
        assert daftar["terbuka"] and daftar["laporan"][0]["id"] == lap["id"]
        r = client.post("/api/v1/analytics/accreditation/laporan", json={"prodi_id": "mei", "dokumen": "LED", "tahun": 2027})
        assert r.status_code == 200 and r.json()["nama"] == "LED 2027"
        assert client.get("/api/v1/analytics/accreditation/admin/reset").status_code == 403  # bukan admin
    finally:
        app.dependency_overrides.clear()
        app.dependency_overrides.update(sebelumnya)
