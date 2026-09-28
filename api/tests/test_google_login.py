"""Uji masuk dengan Google (services/google_login.py): pemeriksaan klaim, pencocokan akun, dan sesi."""
from __future__ import annotations

import base64
import json
import time
from datetime import datetime

import pytest
from sqlalchemy import create_engine, text
from sqlalchemy.pool import StaticPool

from app.services import accreditation_auth, dampak_auth
from app.services import google_login as gl

CLIENT = "klien-uji.apps.googleusercontent.com"


@pytest.fixture()
def engine():
    eng = create_engine("sqlite+pysqlite:///:memory:", poolclass=StaticPool, connect_args={"check_same_thread": False})
    dampak_auth.ensure_schema(eng)
    with eng.begin() as conn:
        conn.execute(text("""CREATE TABLE akreditasi_users (id INTEGER PRIMARY KEY AUTOINCREMENT, email VARCHAR(254) UNIQUE,
            nama VARCHAR(100), password_hash VARCHAR(255), auth_provider VARCHAR(32), is_admin BOOLEAN, is_blocked BOOLEAN,
            created_at TIMESTAMP, last_login_at TIMESTAMP)"""))
        conn.execute(text("CREATE TABLE akreditasi_sessions (token_hash CHAR(64), user_id INTEGER, created_at TIMESTAMP, expires_at TIMESTAMP)"))
        conn.execute(text("INSERT INTO akreditasi_users (email, nama, password_hash, auth_provider, is_admin, is_blocked, created_at) "
                          "VALUES ('lama@ugm.ac.id', 'Akun Lama', 'x', 'local', TRUE, FALSE, :t), "
                          "('blokir@ugm.ac.id', 'Blokir', 'x', 'local', FALSE, TRUE, :t)"), {"t": datetime.now()})
    return eng


@pytest.fixture(autouse=True)
def konfigurasi(monkeypatch):
    monkeypatch.setenv("GOOGLE_CLIENT_ID", CLIENT)
    monkeypatch.setenv("GOOGLE_CLIENT_SECRET", "rahasia-uji")
    monkeypatch.delenv("GOOGLE_REDIRECT_URI", raising=False)


def _id_token(**klaim) -> str:
    isi = {"iss": "https://accounts.google.com", "aud": CLIENT, "exp": time.time() + 600,
           "email_verified": True, "name": "Staf Baru", **klaim}
    b64 = lambda d: base64.urlsafe_b64encode(json.dumps(d).encode()).rstrip(b"=").decode()
    return f"{b64({'alg': 'RS256'})}.{b64(isi)}.tanda-tangan"


def _alur(engine, portal: str, **klaim):
    _url, nilai = gl.mulai(portal, "http://127.0.0.1:3000" + gl.CALLBACK_PATH)
    cookie = gl.baca_cookie(nilai)
    klaim.setdefault("nonce", cookie["nonce"])
    return gl.selesaikan(engine, "kode", cookie["state"], cookie, "http://127.0.0.1:3000" + gl.CALLBACK_PATH,
                         tukar=lambda *a: {"id_token": _id_token(**klaim)})


def test_url_google_berisi_pkce_dan_state():
    url, nilai = gl.mulai("dampak", "http://127.0.0.1:3000" + gl.CALLBACK_PATH)
    cookie = gl.baca_cookie(nilai)
    assert cookie["portal"] == "dampak"
    assert f"state={cookie['state']}" in url and "code_challenge_method=S256" in url and cookie["verifier"] not in url
    assert gl.baca_cookie("rusak") is None and gl.baca_cookie("lain.a.b.c") is None


def test_akun_lama_dicocokkan_lewat_email(engine):
    portal, user, token = _alur(engine, "akreditasi", email="Lama@UGM.ac.id")
    assert portal == "akreditasi" and user["nama"] == "Akun Lama" and user["is_admin"] is True
    assert accreditation_auth.user_from_token(engine, token)["email"] == "lama@ugm.ac.id"
    with engine.connect() as conn:
        assert conn.execute(text("SELECT COUNT(*) FROM akreditasi_users")).scalar() == 2


def test_email_ugm_baru_dibuatkan_akun_dan_akun_pertama_jadi_admin(engine):
    _portal, user, token = _alur(engine, "dampak", email="baru@mail.ugm.ac.id")
    assert user["is_admin"] is True  # portal Dampak masih kosong -> akun pertama
    assert dampak_auth.user_from_token(engine, token)["id"] == user["id"]
    _portal, kedua, _ = _alur(engine, "dampak", email="kedua@ugm.ac.id")
    assert kedua["is_admin"] is False
    with engine.connect() as conn:
        row = conn.execute(text("SELECT auth_provider, password_hash FROM dampak_users WHERE email = 'kedua@ugm.ac.id'")).first()
    assert tuple(row) == ("google", None)
    # Akun Google tanpa password tidak bisa dipakai login password.
    assert dampak_auth.login(engine, "kedua@ugm.ac.id", "apa saja")[0] is None


@pytest.mark.parametrize("klaim, pesan", [
    ({"email": "orang@gmail.com"}, "bukan email UGM"),
    ({"email": "x@ugm.ac.id", "email_verified": False}, "belum terverifikasi"),
    ({"email": "x@ugm.ac.id", "aud": "klien-lain"}, "tidak ditujukan"),
    ({"email": "x@ugm.ac.id", "nonce": "palsu"}, "tidak cocok"),
    ({"email": "x@ugm.ac.id", "exp": time.time() - 5}, "kedaluwarsa"),
    ({"email": "blokir@ugm.ac.id"}, "diblokir"),
])
def test_klaim_atau_akun_ditolak(engine, klaim, pesan):
    with pytest.raises(gl.GoogleLoginError, match=pesan):
        _alur(engine, "akreditasi", **klaim)
    with engine.connect() as conn:
        assert conn.execute(text("SELECT COUNT(*) FROM akreditasi_sessions")).scalar() == 0


def test_state_harus_sama_dengan_cookie(engine):
    _url, nilai = gl.mulai("akreditasi", "http://x" + gl.CALLBACK_PATH)
    cookie = gl.baca_cookie(nilai)
    with pytest.raises(gl.GoogleLoginError, match="tidak cocok"):
        gl.selesaikan(engine, "kode", "state-lain", cookie, "http://x", tukar=lambda *a: pytest.fail("tidak boleh menukar kode"))
    with pytest.raises(gl.GoogleLoginError):
        gl.selesaikan(engine, "kode", cookie["state"], None, "http://x", tukar=lambda *a: pytest.fail("tidak boleh menukar kode"))


def test_konfigurasi_dari_file_json(tmp_path, monkeypatch):
    monkeypatch.delenv("GOOGLE_CLIENT_ID"); monkeypatch.delenv("GOOGLE_CLIENT_SECRET")
    assert not gl.aktif()
    berkas = tmp_path / "client_secret.json"
    berkas.write_text(json.dumps({"web": {"client_id": "dari-file", "client_secret": "s"}}), encoding="utf-8")
    monkeypatch.setenv("GOOGLE_CLIENT_SECRET_FILE", str(berkas))
    assert gl.konfigurasi() == {"client_id": "dari-file", "client_secret": "s"}
    monkeypatch.setenv("GOOGLE_REDIRECT_URI", "https://dts-lab.web.id/cb")
    assert gl.redirect_uri("http://abaikan") == "https://dts-lab.web.id/cb"


def test_tujuan_kembali_hanya_di_portal_sendiri():
    assert gl.tujuan_aman("akreditasi", "/akreditasi?laporan=5")
    assert gl.tujuan_aman("dampak", "/dampak/admin")
    for buruk in ("https://jahat.id", "//jahat.id", "/dampak", "/akreditasi-palsu", "/akreditasi/\\x", "/akreditasi\n", ""):
        assert not gl.tujuan_aman("akreditasi", buruk), buruk
