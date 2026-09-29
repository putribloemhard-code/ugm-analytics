"""Akun baru di skema server lama (kolom id tanpa nomor otomatis) tidak boleh tersimpan diam-diam
dengan id NULL; login akun ber-id NULL memberi pesan jelas. Perbaikan PostgreSQL-nya sendiri ada
di services/perbaikan_skema.py (tidak berlaku di SQLite)."""
from __future__ import annotations

from datetime import datetime

import bcrypt
import pytest
from sqlalchemy import create_engine, text
from sqlalchemy.pool import StaticPool

from app.services import accreditation_auth, dampak_auth, perbaikan_skema


@pytest.fixture()
def engine_lama():
    """Tiruan tabel hasil `to_sql` lama: `id INTEGER` biasa, tanpa PRIMARY KEY/IDENTITY."""
    eng = create_engine("sqlite+pysqlite:///:memory:", poolclass=StaticPool, connect_args={"check_same_thread": False})
    with eng.begin() as conn:
        for users, sesi in (("akreditasi_users", "akreditasi_sessions"), ("dampak_users", "dampak_sessions")):
            conn.execute(text(f"""CREATE TABLE {users} (id INTEGER, email VARCHAR(254) UNIQUE, nama VARCHAR(100),
                password_hash VARCHAR(255), auth_provider VARCHAR(32), is_admin BOOLEAN, is_blocked BOOLEAN,
                created_at TIMESTAMP, last_login_at TIMESTAMP)"""))
            conn.execute(text(f"CREATE TABLE {sesi} (token_hash CHAR(64), user_id INTEGER, created_at TIMESTAMP, expires_at TIMESTAMP)"))
            conn.execute(text(f"INSERT INTO {users} VALUES (1, 'lama@ugm.ac.id', 'Lama', :h, 'local', 1, 0, :t, NULL)"),
                         {"h": bcrypt.hashpw(b"password-lama", bcrypt.gensalt(rounds=4)).decode(), "t": datetime.now()})
        conn.execute(text("CREATE TABLE akreditasi_login_attempts (id INTEGER PRIMARY KEY AUTOINCREMENT, email VARCHAR(254), "
                          "berhasil BOOLEAN, attempted_at TIMESTAMP)"))
    return eng


@pytest.mark.parametrize("auth, tabel", [(accreditation_auth, "akreditasi_users"), (dampak_auth, "dampak_users")])
def test_daftar_di_skema_lama_ditolak_tanpa_menyimpan_akun_rusak(engine_lama, auth, tabel):
    ok, pesan = auth.register(engine_lama, "baru@ugm.ac.id", "Baru", "password-baru")
    assert not ok and "nomor ID" in pesan
    with engine_lama.connect() as conn:
        assert conn.execute(text(f"SELECT COUNT(*) FROM {tabel} WHERE email = 'baru@ugm.ac.id'")).scalar() == 0
    # Akun lama (punya id) tetap bisa login seperti biasa.
    user, _, token = auth.login(engine_lama, "lama@ugm.ac.id", "password-lama")
    assert user and user["id"] == 1 and auth.user_from_token(engine_lama, token)["email"] == "lama@ugm.ac.id"


@pytest.mark.parametrize("auth, tabel", [(accreditation_auth, "akreditasi_users"), (dampak_auth, "dampak_users")])
def test_login_akun_ber_id_kosong_memberi_pesan_jelas(engine_lama, auth, tabel):
    with engine_lama.begin() as conn:
        conn.execute(text(f"INSERT INTO {tabel} (email, nama, password_hash, auth_provider, is_admin, is_blocked, created_at) "
                          "VALUES ('yatim@ugm.ac.id', 'Yatim', :h, 'local', 0, 0, :t)"),
                     {"h": bcrypt.hashpw(b"password-yatim", bcrypt.gensalt(rounds=4)).decode(), "t": datetime.now()})
    user, pesan, token = auth.login(engine_lama, "yatim@ugm.ac.id", "password-yatim")
    assert user is None and token is None and "nomor ID" in pesan


def test_perbaikan_hanya_untuk_postgresql(engine_lama):
    assert perbaikan_skema.perbaiki(engine_lama) == []
    assert perbaikan_skema._q('akun"x') == '"akun""x"'
