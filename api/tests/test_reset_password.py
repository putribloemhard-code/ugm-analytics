"""Uji lupa password (services/reset_password.py) dan halaman Admin Dampak (services/dampak_account.py)."""
from __future__ import annotations

from datetime import datetime, timedelta

import bcrypt
import pytest
from sqlalchemy import create_engine, text
from sqlalchemy.pool import StaticPool

from app.services import reset_password as rp
from app.services.accreditation_account import AksiDitolak
from app.services.dampak_account import DampakAccountService
from app.services.dampak_auth import ensure_schema as ensure_dampak

BASE = "http://127.0.0.1:3000"


@pytest.fixture()
def engine():
    eng = create_engine("sqlite+pysqlite:///:memory:", poolclass=StaticPool, connect_args={"check_same_thread": False})
    ensure_dampak(eng)
    with eng.begin() as conn:
        conn.execute(text("""CREATE TABLE akreditasi_users (id INTEGER PRIMARY KEY, email VARCHAR(254), nama VARCHAR(100),
            password_hash VARCHAR(255), is_admin BOOLEAN, is_blocked BOOLEAN, auth_provider VARCHAR(32) DEFAULT 'local')"""))
        conn.execute(text("CREATE TABLE akreditasi_sessions (token_hash CHAR(64), user_id INTEGER, created_at TIMESTAMP, expires_at TIMESTAMP)"))
        h = bcrypt.hashpw(b"lama12345", bcrypt.gensalt()).decode()
        conn.execute(text("INSERT INTO akreditasi_users (id, email, nama, password_hash, is_admin, is_blocked) VALUES (1, 'admin@ugm.ac.id', 'Admin', :h, 1, 0), "
                          "(2, 'staf@ugm.ac.id', 'Staf', :h, 0, 0), (3, 'blokir@ugm.ac.id', 'Blokir', :h, 0, 1)"), {"h": h})
        conn.execute(text("INSERT INTO akreditasi_sessions VALUES ('s1', 2, :t, :t)"), {"t": datetime.now()})
        for i, (email, admin) in enumerate((("putri@mail.ugm.ac.id", True), ("tim@ugm.ac.id", False)), start=14):
            conn.execute(text("INSERT INTO dampak_users (id, email, nama, password_hash, auth_provider, is_admin, is_blocked, created_at) "
                              "VALUES (:i, :e, :n, :h, 'local', :a, FALSE, :t)"),
                         {"i": i, "e": email, "n": email.split("@")[0], "h": h, "a": admin, "t": datetime.now()})
    rp.ensure_schema(eng)
    rp.ensure_schema(eng)  # idempoten
    return eng


@pytest.fixture()
def token_tetap(monkeypatch):
    daftar = iter(f"token-uji-{i}" for i in range(100))
    monkeypatch.setattr(rp.secrets, "token_urlsafe", lambda n=32: next(daftar))
    monkeypatch.setattr(rp.mailer, "terkonfigurasi", lambda: False)


def _jumlah_token(engine) -> int:
    with engine.connect() as conn:
        return conn.execute(text("SELECT COUNT(*) FROM reset_password_token")).scalar()


def test_jawaban_sama_untuk_email_ada_dan_tidak(engine, token_tetap):
    a = rp.minta_reset(engine, "akreditasi", "staf@ugm.ac.id", BASE)
    b = rp.minta_reset(engine, "akreditasi", "tidak-ada@ugm.ac.id", BASE)
    c = rp.minta_reset(engine, "akreditasi", "blokir@ugm.ac.id", BASE)
    assert a == b == c == {"message": rp.JAWABAN_UMUM}
    assert _jumlah_token(engine) == 1  # hanya akun aktif yang dibuatkan token
    with pytest.raises(rp.ResetError):
        rp.minta_reset(engine, "lain", "staf@ugm.ac.id", BASE)


def test_reset_lewat_tautan_sekali_pakai_dan_mengakhiri_sesi(engine, token_tetap):
    rp.minta_reset(engine, "akreditasi", "Staf@UGM.ac.id ", BASE)
    assert rp.cek(engine, "akreditasi", "token-uji-0")["email"] == "staf@ugm.ac.id"
    with pytest.raises(rp.ResetError):  # password terlalu pendek
        rp.reset(engine, "akreditasi", "token-uji-0", "pendek")
    rp.reset(engine, "akreditasi", "token-uji-0", "baru-12345")
    with engine.connect() as conn:
        h = conn.execute(text("SELECT password_hash FROM akreditasi_users WHERE id = 2")).scalar()
        assert bcrypt.checkpw(b"baru-12345", h.encode())
        assert conn.execute(text("SELECT COUNT(*) FROM akreditasi_sessions WHERE user_id = 2")).scalar() == 0
    with pytest.raises(rp.ResetError):  # sekali pakai
        rp.reset(engine, "akreditasi", "token-uji-0", "lagi-12345")
    with pytest.raises(rp.ResetError):  # token portal lain tidak berlaku
        rp.cek(engine, "dampak", "token-uji-0")


def test_tautan_baru_menggugurkan_yang_lama_dan_kedaluwarsa(engine, token_tetap):
    rp.minta_reset(engine, "dampak", "tim@ugm.ac.id", BASE)
    rp.minta_reset(engine, "dampak", "tim@ugm.ac.id", BASE)
    with pytest.raises(rp.ResetError):
        rp.cek(engine, "dampak", "token-uji-0")
    assert rp.cek(engine, "dampak", "token-uji-1")["nama"] == "tim"
    with engine.begin() as conn:
        conn.execute(text("UPDATE reset_password_token SET expires_at = :t"), {"t": datetime.now() - timedelta(minutes=1)})
    with pytest.raises(rp.ResetError):
        rp.cek(engine, "dampak", "token-uji-1")


def test_batas_tiga_permintaan_per_jam(engine, token_tetap):
    for _ in range(5):
        rp.minta_reset(engine, "dampak", "tim@ugm.ac.id", BASE)
    assert _jumlah_token(engine) == 3


def test_tautan_dari_admin(engine, token_tetap):
    hasil = rp.buat_tautan_admin(engine, "akreditasi", {"id": 1, "email": "admin@ugm.ac.id"}, 2, BASE)
    assert hasil["tautan"] == f"{BASE}/reset-password?portal=akreditasi&token=token-uji-0"
    rp.reset(engine, "akreditasi", "token-uji-0", "dari-admin-1")
    with pytest.raises(PermissionError):  # bukan admin
        rp.buat_tautan_admin(engine, "akreditasi", {"id": 2, "email": "staf@ugm.ac.id"}, 1, BASE)
    with pytest.raises(rp.ResetError):
        rp.buat_tautan_admin(engine, "dampak", {"id": 14, "email": "putri@mail.ugm.ac.id"}, 999, BASE)


def test_admin_dampak(engine):
    svc = DampakAccountService(engine)
    putri, tim = {"id": 14, "email": "putri@mail.ugm.ac.id"}, {"id": 15, "email": "tim@ugm.ac.id"}
    data = svc.admin_overview(putri)
    assert data["summary"] == {"total_akun": 2, "admin": 1, "diblokir": 0}
    assert [u["diri_sendiri"] for u in data["users"]] == [True, False]
    with pytest.raises(AksiDitolak):  # bukan admin
        svc.admin_overview(tim)
    with pytest.raises(AksiDitolak):  # akun sendiri
        svc.admin_action(putri, "hapus", 14)
    svc.admin_action(putri, "blokir", 15, True)
    assert svc.admin_overview(putri)["summary"]["diblokir"] == 1
    svc.admin_action(putri, "hapus", 15)
    assert svc.admin_overview(putri)["summary"]["total_akun"] == 1
