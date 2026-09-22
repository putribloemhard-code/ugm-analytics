"""Uji gerbang akun Analisis Dampak (services/dampak_auth.py + endpoint /analytics/dampak/auth/*).

Semua uji memakai SQLite sementara di memori, jadi tidak menyentuh MySQL asli.

Latar bug yang dijaga di sini (2026-09-22): DDL `ensure_schema` dulu memakai
`CREATE INDEX IF NOT EXISTS` (khusus PostgreSQL) sehingga di MySQL -- yang dipakai pratinjau
lokal lewat `web/dev_api_mysql.py` -- seluruh registrasi/login gagal 500 dan tombol "Buat akun"
di halaman login Analisis Dampak tidak pernah berhasil.
"""
from __future__ import annotations

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine, text

from app.services import dampak_auth

EMAIL, NAMA, SANDI = "dosen.uji@ugm.ac.id", "Dosen Uji", "RahasiaUji123"


@pytest.fixture()
def engine(tmp_path):
    """SQLite berbasis BERKAS (bukan :memory:) supaya tabel tetap ada saat TestClient
    menjalankan request di thread lain -- dengan :memory:, tiap koneksi baru dapat DB kosong."""
    eng = create_engine(f"sqlite+pysqlite:///{(tmp_path / 'dampak-uji.sqlite').as_posix()}",
                        connect_args={"check_same_thread": False})
    dampak_auth.ensure_schema(eng)
    return eng


def test_ensure_schema_membuat_tabel_dan_index(engine):
    with engine.connect() as conn:
        tabel = {row[0] for row in conn.execute(text(
            "SELECT name FROM sqlite_master WHERE type = 'table'"))}
        assert {"dampak_users", "dampak_sessions"} <= tabel
        index = {row[0] for row in conn.execute(text(
            "SELECT name FROM sqlite_master WHERE type = 'index'"))}
        assert {"dampak_sessions_user_idx", "dampak_sessions_expires_idx"} <= index
    # Idempoten: dipanggil ulang tidak boleh meledak (endpoint memanggilnya tiap request).
    dampak_auth.ensure_schema(engine)
    dampak_auth.ensure_schema(engine)


def test_ensure_schema_membuat_ulang_tabel_yang_terhapus(engine):
    """API yang hidup saat tabelnya hilang harus sembuh sendiri tanpa restart (dulu tabel hanya
    dibuat sekali per proses, jadi endpoint balas 500 selamanya)."""
    with engine.begin() as conn:
        conn.execute(text("DROP TABLE dampak_sessions"))
        conn.execute(text("DROP TABLE dampak_users"))
    dampak_auth.ensure_schema(engine)
    ok, _ = dampak_auth.register(engine, "sembuh@ugm.ac.id", "Sembuh", "rahasia123")
    assert ok is True


def test_ddl_index_memakai_bentuk_yang_dikenal_mysql_dan_postgres():
    """Inti bug: `CREATE INDEX IF NOT EXISTS` ditolak MySQL (error 1064)."""
    mysql = create_engine("mysql+pymysql://u:p@localhost/db")          # tidak connect, hanya dialek
    postgres = create_engine("postgresql+psycopg://u:p@localhost/db")
    ddl_mysql = dampak_auth._index_ddl(mysql)[0]
    ddl_postgres = dampak_auth._index_ddl(postgres)[0]
    assert "IF NOT EXISTS" not in ddl_mysql
    assert ddl_mysql.startswith("CREATE INDEX dampak_sessions_user_idx ON dampak_sessions")
    assert "IF NOT EXISTS" in ddl_postgres
    # Tabel: `SERIAL` hanya ada di PostgreSQL, MySQL butuh AUTO_INCREMENT.
    assert "AUTO_INCREMENT" in dampak_auth._table_ddl(mysql)[0]
    assert "SERIAL" not in dampak_auth._table_ddl(mysql)[0]
    assert "SERIAL" in dampak_auth._table_ddl(postgres)[0]


def test_registrasi_lalu_login_lalu_logout(engine):
    ok, pesan = dampak_auth.register(engine, EMAIL, NAMA, SANDI)
    assert ok is True and "berhasil" in pesan

    # Akun pertama otomatis admin, sama seperti jalur akreditasi.
    ok_ulang, pesan_ulang = dampak_auth.register(engine, EMAIL, NAMA, SANDI)
    assert ok_ulang is False and pesan_ulang == "Email sudah terdaftar."
    with engine.connect() as conn:
        assert conn.execute(text("SELECT is_admin FROM dampak_users WHERE email = :e"),
                            {"e": EMAIL}).scalar() == 1

    user, salah, token = dampak_auth.login(engine, EMAIL, "sandi-salah")
    assert user is None and salah == "Email atau password salah." and token is None

    user, salah, token = dampak_auth.login(engine, EMAIL.upper(), SANDI)  # email dinormalkan
    assert salah is None and token and user["nama"] == NAMA and user["is_admin"] is True

    aktif = dampak_auth.user_from_token(engine, token)
    assert aktif and aktif["email"] == EMAIL and aktif["id"] == user["id"]

    dampak_auth.logout(engine, token)
    assert dampak_auth.user_from_token(engine, token) is None


def test_domain_email_dibatasi_ugm(engine):
    for email, pesan in (
        ("orang@gmail.com", "Gunakan email @ugm.ac.id atau @mail.ugm.ac.id."),
        ("admin@ugm.ac.id.evil.com", "Gunakan email @ugm.ac.id atau @mail.ugm.ac.id."),
        ("admin@notugm.ac.id", "Gunakan email @ugm.ac.id atau @mail.ugm.ac.id."),
    ):
        ok, pesan_asli = dampak_auth.register(engine, email, NAMA, SANDI)
        assert ok is False and pesan_asli == pesan
    ok, _ = dampak_auth.register(engine, "mhs@mail.ugm.ac.id", NAMA, SANDI)
    assert ok is True


def test_akun_diblokir_tidak_bisa_login(engine):
    dampak_auth.register(engine, EMAIL, NAMA, SANDI)
    with engine.begin() as conn:
        conn.execute(text("UPDATE dampak_users SET is_blocked = TRUE WHERE email = :e"), {"e": EMAIL})
    user, pesan, token = dampak_auth.login(engine, EMAIL, SANDI)
    assert user is None and token is None and "diblokir" in pesan


@pytest.fixture()
def client(engine, monkeypatch):
    """API uji yang memakai engine SQLite, bukan MySQL asli.

    `app.db.get_engine` di-patch supaya tidak ada satu pun jalur yang menyentuh DB asli;
    TestClient dipakai tanpa context manager agar lifespan (yang menyiapkan skema di DB asli)
    tidak dijalankan.
    """
    import app.db as db
    from app.main import app

    monkeypatch.setattr(db, "get_engine", lambda: engine)
    monkeypatch.setattr("app.api.v1.analytics.get_engine", lambda: engine)
    return TestClient(app)


def test_endpoint_register_lalu_login_berhasil(client):
    daftar = client.post("/api/v1/analytics/dampak/auth/register",
                         json={"email": EMAIL, "name": NAMA, "password": SANDI})
    assert daftar.status_code == 200, daftar.text
    assert "berhasil" in daftar.json()["message"]

    masuk = client.post("/api/v1/analytics/dampak/auth/login", json={"email": EMAIL, "password": SANDI})
    assert masuk.status_code == 200, masuk.text
    assert masuk.json()["user"]["email"] == EMAIL
    assert dampak_auth.COOKIE_NAME in masuk.cookies

    saya = client.get("/api/v1/analytics/dampak/auth/me")
    assert saya.status_code == 200 and saya.json()["user"]["email"] == EMAIL

    keluar = client.post("/api/v1/analytics/dampak/auth/logout")
    assert keluar.status_code == 200


def test_endpoint_register_menolak_email_duplikat_dan_non_ugm(client):
    body = {"email": EMAIL, "name": NAMA, "password": SANDI}
    assert client.post("/api/v1/analytics/dampak/auth/register", json=body).status_code == 200
    ulang = client.post("/api/v1/analytics/dampak/auth/register", json=body)
    assert ulang.status_code == 400 and ulang.json()["detail"] == "Email sudah terdaftar."
    asing = client.post("/api/v1/analytics/dampak/auth/register",
                        json={**body, "email": "orang@gmail.com"})
    assert asing.status_code == 400 and "ugm.ac.id" in asing.json()["detail"]


def test_endpoint_me_tanpa_sesi_401(client):
    assert client.get("/api/v1/analytics/dampak/auth/me").status_code == 401
