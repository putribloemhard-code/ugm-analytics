"""Login Analisis Dampak -- gerbang akun yang TERPISAH TOTAL dari akun Akreditasi.

Pola, skema kolom, dan alur sama persis dengan `accreditation_auth.py` (bcrypt + token acak +
tabel sesi berisi hash token, bukan tokennya), tapi tabel dan cookie-nya sendiri
(`dampak_users`/`dampak_sessions`/cookie `dampak_sid`) supaya login di satu portal tidak
membuka portal yang lain.

CATATAN DIALEK (perbaikan 2026-09-22): DDL di sini WAJIB jalan di MySQL (pratinjau lokal,
`web/dev_api_mysql.py`) DAN PostgreSQL (produksi). `CREATE INDEX IF NOT EXISTS` hanya dikenal
PostgreSQL -- di MySQL error 1064 dan SELURUH registrasi/login gagal 500 karena `ensure_schema`
dipanggil di awal kedua endpoint itu. Karena itu DDL dirakit lewat `services/sqlcompat.py`.
"""

from __future__ import annotations

import hashlib
import re
import secrets
from datetime import datetime, timedelta
from typing import Any

import bcrypt
from sqlalchemy import text
from sqlalchemy.engine import Engine

from app.services import sqlcompat

COOKIE_NAME = "dampak_sid"
SESSION_AGE = timedelta(hours=12)
ALLOWED_DOMAINS = {"ugm.ac.id", "mail.ugm.ac.id"}
EMAIL_RE = re.compile(r"^[a-z0-9._%+\-]+@([a-z0-9.-]+)$")


def normalize_email(email: str) -> str:
    return (email or "").strip().lower()


def valid_email(email: str) -> bool:
    match = EMAIL_RE.fullmatch(normalize_email(email))
    return bool(match and match.group(1) in ALLOWED_DOMAINS and len(email) <= 254)


def token_hash(token: str) -> str:
    return hashlib.sha256(token.encode("ascii")).hexdigest()


def _table_ddl(engine: Engine) -> list[str]:
    """CREATE TABLE per dialek. `SERIAL` hanya ada di PostgreSQL dan `AUTO_INCREMENT` hanya di
    MySQL, jadi kuncinya dirakit di sini. Tanpa FOREIGN KEY: MySQL mengabaikan `REFERENCES`
    inline sehingga perilakunya beda dengan PostgreSQL -- sesi cukup diindeks, sama seperti
    `akreditasi_sessions`."""
    id_clause = {
        "postgresql": "SERIAL PRIMARY KEY",
        "mysql": "INTEGER NOT NULL AUTO_INCREMENT PRIMARY KEY",
        "sqlite": "INTEGER NOT NULL PRIMARY KEY AUTOINCREMENT",
    }.get(engine.dialect.name, "INTEGER NOT NULL PRIMARY KEY")
    return [
        f"""
        CREATE TABLE IF NOT EXISTS dampak_users (
            id {id_clause},
            email VARCHAR(254) NOT NULL UNIQUE,
            nama VARCHAR(100) NOT NULL,
            password_hash VARCHAR(255) NULL,
            auth_provider VARCHAR(32) NOT NULL DEFAULT 'local',
            is_admin BOOLEAN NOT NULL DEFAULT FALSE,
            is_blocked BOOLEAN NOT NULL DEFAULT FALSE,
            created_at TIMESTAMP NOT NULL,
            last_login_at TIMESTAMP NULL
        )
        """,
        """
        CREATE TABLE IF NOT EXISTS dampak_sessions (
            token_hash CHAR(64) NOT NULL PRIMARY KEY,
            user_id INTEGER NOT NULL,
            created_at TIMESTAMP NOT NULL,
            expires_at TIMESTAMP NOT NULL
        )
        """,
    ]


def _index_ddl(engine: Engine) -> list[str]:
    return [
        sqlcompat.index_ddl(engine, "dampak_sessions", ["user_id"], name="dampak_sessions_user_idx"),
        sqlcompat.index_ddl(engine, "dampak_sessions", ["expires_at"], name="dampak_sessions_expires_idx"),
    ]


def ensure_schema(engine: Engine) -> None:
    """Buat tabel akun login Dampak bila belum ada. Idempoten di MySQL, PostgreSQL, dan SQLite;
    tidak ada tabel akreditasi_* yang disentuh sama sekali.

    Sengaja TANPA cache "sudah pernah disiapkan": DDL-nya murah (CREATE TABLE IF NOT EXISTS +
    dua CREATE INDEX), sedangkan cache membuat API yang tabelnya terhapus di tengah jalan balas
    500 selamanya sampai di-restart (terbukti 2026-09-22).
    """
    with engine.begin() as conn:
        for ddl in _table_ddl(engine):
            conn.execute(text(ddl))
    for ddl in _index_ddl(engine):
        try:
            with engine.begin() as conn:
                conn.execute(text(ddl))
        except Exception as exc:  # noqa: BLE001 - index duplikat = sudah ada, bukan kegagalan
            if not sqlcompat.is_duplicate_index_error(exc):
                raise


def user_from_token(engine: Engine, token: str | None) -> dict[str, Any] | None:
    if not token:
        return None
    with engine.connect() as conn:
        row = conn.execute(text("""
            SELECT u.id, u.email, u.nama, u.is_admin
            FROM dampak_sessions s
            JOIN dampak_users u ON u.id = s.user_id
            WHERE s.token_hash = :hash AND s.expires_at > :now AND u.is_blocked = FALSE
        """), {"hash": token_hash(token), "now": datetime.now()}).mappings().first()
    return dict(row) if row else None


def login(engine: Engine, email: str, password: str) -> tuple[dict[str, Any] | None, str | None, str | None]:
    email = normalize_email(email)
    with engine.connect() as conn:
        row = conn.execute(text("""
            SELECT id, email, nama, password_hash, auth_provider, is_admin, is_blocked
            FROM dampak_users WHERE email = :email
        """), {"email": email}).mappings().first()
    if not row:
        bcrypt.checkpw(password.encode()[:72], bcrypt.hashpw(b"dummy", bcrypt.gensalt(rounds=4)))
        return None, "Email atau password salah.", None
    stored = row["password_hash"].encode() if row["password_hash"] else None
    ok = bool(stored and row["auth_provider"] == "local" and bcrypt.checkpw(password.encode()[:72], stored))
    if not ok:
        return None, "Email atau password salah.", None
    if row["is_blocked"]:
        return None, "Akun Anda diblokir, hubungi admin.", None
    now = datetime.now()
    token = secrets.token_urlsafe(32)
    with engine.begin() as conn:
        conn.execute(text("DELETE FROM dampak_sessions WHERE expires_at < :now"), {"now": now})
        conn.execute(text("""
            INSERT INTO dampak_sessions (token_hash, user_id, created_at, expires_at)
            VALUES (:hash, :user_id, :created, :expires)
        """), {"hash": token_hash(token), "user_id": row["id"], "created": now, "expires": now + SESSION_AGE})
        conn.execute(text("UPDATE dampak_users SET last_login_at = :now WHERE id = :id"), {"now": now, "id": row["id"]})
    return {"id": row["id"], "email": row["email"], "nama": row["nama"], "is_admin": bool(row["is_admin"])}, None, token


def register(engine: Engine, email: str, name: str, password: str) -> tuple[bool, str]:
    email, name = normalize_email(email), (name or "").strip()
    if not valid_email(email): return False, "Gunakan email @ugm.ac.id atau @mail.ugm.ac.id."
    if not name or len(name) > 100: return False, "Nama wajib diisi dan maksimal 100 karakter."
    if len(password) < 8 or len(password.encode()) > 72: return False, "Password harus 8–72 byte."
    now = datetime.now()
    try:
        with engine.begin() as conn:
            conn.execute(text("""
                INSERT INTO dampak_users (email, nama, password_hash, auth_provider, is_admin, is_blocked, created_at)
                VALUES (:email, :name, :hash, 'local', FALSE, FALSE, :now)
            """), {"email": email, "name": name, "hash": bcrypt.hashpw(password.encode(), bcrypt.gensalt()).decode(), "now": now})
            # SELECT, bukan RETURNING: RETURNING tidak dikenal MySQL. Email unik, jadi baris ini pasti yang baru.
            new_id = conn.execute(text("SELECT id FROM dampak_users WHERE email = :email"), {"email": email}).scalar_one()
            # Akun pertama jadi admin -- sama seperti akreditasi (akreditasi_auth.register).
            if conn.execute(text("SELECT MIN(id) FROM dampak_users")).scalar() == new_id:
                conn.execute(text("UPDATE dampak_users SET is_admin = TRUE WHERE id = :id"), {"id": new_id})
    except Exception as exc:
        if sqlcompat.is_duplicate_entry_error(exc): return False, "Email sudah terdaftar."
        raise
    return True, "Registrasi berhasil. Silakan login."


def logout(engine: Engine, token: str | None) -> None:
    if token:
        with engine.begin() as conn:
            conn.execute(text("DELETE FROM dampak_sessions WHERE token_hash = :hash"), {"hash": token_hash(token)})
