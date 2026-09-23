from __future__ import annotations

import hashlib
import math
import re
import secrets
from datetime import datetime, timedelta
from pathlib import Path
from typing import Any

import bcrypt
from sqlalchemy import text
from sqlalchemy.engine import Engine

from app.services import sqlcompat

COOKIE_NAME = "akreditasi_sid"
SESSION_AGE = timedelta(hours=12)
# Rate limit (padanan auth_akreditasi.py lama): 5 gagal BERTURUT-TURUT dalam 15 menit -> email
# itu dikunci sementara. Selama terkunci password tidak dicek & percobaan tidak dicatat.
MAX_FAILED = 5
FAILED_WINDOW = timedelta(minutes=15)
ALLOWED_DOMAINS = {"ugm.ac.id", "mail.ugm.ac.id"}
EMAIL_RE = re.compile(r"^[a-z0-9._%+\-]+@([a-z0-9.-]+)$")


def normalize_email(email: str) -> str:
    return (email or "").strip().lower()


def valid_email(email: str) -> bool:
    match = EMAIL_RE.fullmatch(normalize_email(email))
    return bool(match and match.group(1) in ALLOWED_DOMAINS and len(email) <= 254)


def token_hash(token: str) -> str:
    return hashlib.sha256(token.encode("ascii")).hexdigest()


def user_from_token(engine: Engine, token: str | None) -> dict[str, Any] | None:
    if not token:
        return None
    with engine.connect() as conn:
        row = conn.execute(text("""
            SELECT u.id, u.email, u.nama, u.is_admin
            FROM akreditasi_sessions s
            JOIN akreditasi_users u ON u.id = s.user_id
            WHERE s.token_hash = :hash AND s.expires_at > :now AND u.is_blocked = FALSE
        """), {"hash": token_hash(token), "now": datetime.now()}).mappings().first()
    return dict(row) if row else None


def lockout_seconds(conn, email: str, now: datetime | None = None) -> int | None:
    """Detik tersisa sampai email ini boleh mencoba login lagi, atau None bila tidak terkunci.

    Terkunci = MAX_FAILED percobaan TERAKHIR dalam FAILED_WINDOW semuanya gagal
    (satu yang berhasil memutus rentetan).
    """
    now = now or datetime.now()
    rows = conn.execute(text("""
        SELECT berhasil, attempted_at FROM akreditasi_login_attempts
        WHERE email = :email AND attempted_at >= :since
        ORDER BY attempted_at DESC, id DESC LIMIT :n
    """), {"email": email, "since": now - FAILED_WINDOW, "n": MAX_FAILED}).all()
    if len(rows) < MAX_FAILED or any(bool(r.berhasil) for r in rows):
        return None
    oldest = rows[-1].attempted_at
    if isinstance(oldest, str):  # SQLite (uji) mengembalikan teks
        oldest = datetime.fromisoformat(oldest)
    remaining = (oldest + FAILED_WINDOW - now).total_seconds()
    return math.ceil(remaining) if remaining > 0 else None


def record_attempt(conn, email: str, success: bool, now: datetime | None = None) -> None:
    now = now or datetime.now()
    conn.execute(text("""
        INSERT INTO akreditasi_login_attempts (email, berhasil, attempted_at) VALUES (:email, :ok, :now)
    """), {"email": email[:254], "ok": bool(success), "now": now})
    # Rate limit hanya butuh 15 menit terakhir; buang jejak yang lebih tua dari sehari.
    conn.execute(text("DELETE FROM akreditasi_login_attempts WHERE attempted_at < :limit"),
                 {"limit": now - timedelta(days=1)})


def login(engine: Engine, email: str, password: str) -> tuple[dict[str, Any] | None, str | None, str | None]:
    email = normalize_email(email)
    with engine.connect() as conn:
        remaining = lockout_seconds(conn, email)
    if remaining:
        return None, (f"Terlalu banyak percobaan login gagal untuk email ini. "
                      f"Coba lagi dalam {math.ceil(remaining / 60)} menit."), None
    with engine.connect() as conn:
        row = conn.execute(text("""
            SELECT id, email, nama, password_hash, auth_provider, is_admin, is_blocked
            FROM akreditasi_users WHERE email = :email
        """), {"email": email}).mappings().first()
    if not row:
        bcrypt.checkpw(password.encode()[:72], bcrypt.hashpw(b"dummy", bcrypt.gensalt(rounds=4)))
        ok = False
    else:
        stored = row["password_hash"].encode() if row["password_hash"] else None
        ok = bool(stored and row["auth_provider"] == "local" and bcrypt.checkpw(password.encode()[:72], stored))
    if not ok:
        with engine.begin() as conn:
            record_attempt(conn, email, False)
        return None, "Email atau password salah.", None
    if row["is_blocked"]:
        return None, "Akun Anda diblokir, hubungi admin.", None
    now = datetime.now()
    token = secrets.token_urlsafe(32)
    with engine.begin() as conn:
        record_attempt(conn, email, True, now)
        conn.execute(text("DELETE FROM akreditasi_sessions WHERE expires_at < :now"), {"now": now})
        conn.execute(text("""
            INSERT INTO akreditasi_sessions (token_hash, user_id, created_at, expires_at)
            VALUES (:hash, :user_id, :created, :expires)
        """), {"hash": token_hash(token), "user_id": row["id"], "created": now, "expires": now + SESSION_AGE})
        conn.execute(text("UPDATE akreditasi_users SET last_login_at = :now WHERE id = :id"), {"now": now, "id": row["id"]})
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
                INSERT INTO akreditasi_users (email, nama, password_hash, auth_provider, is_admin, is_blocked, created_at)
                VALUES (:email, :name, :hash, 'local', FALSE, FALSE, :now)
            """), {"email": email, "name": name, "hash": bcrypt.hashpw(password.encode(), bcrypt.gensalt()).decode(), "now": now})
            # SELECT, bukan RETURNING: RETURNING tidak dikenal MySQL. Email unik, jadi baris ini pasti yang baru.
            new_id = conn.execute(text("SELECT id FROM akreditasi_users WHERE email = :email"), {"email": email}).scalar_one()
            if conn.execute(text("SELECT MIN(id) FROM akreditasi_users")).scalar() == new_id:
                conn.execute(text("UPDATE akreditasi_users SET is_admin = TRUE WHERE id = :id"), {"id": new_id})
    except Exception as exc:
        if sqlcompat.is_duplicate_entry_error(exc): return False, "Email sudah terdaftar."
        raise
    return True, "Registrasi berhasil. Silakan login."


def logout(engine: Engine, token: str | None) -> None:
    if token:
        with engine.begin() as conn:
            conn.execute(text("DELETE FROM akreditasi_sessions WHERE token_hash = :hash"), {"hash": token_hash(token)})


def safe_filename(name: str) -> str:
    cleaned = re.sub(r"[^A-Za-z0-9._-]+", "_", Path(name or "file").name).strip("_") or "file"
    return cleaned[:240]
