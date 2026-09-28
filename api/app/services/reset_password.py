"""Lupa password untuk dua portal (Akreditasi dan Analisis Dampak) lewat tautan reset sekali pakai.

Alur:
1. Di halaman login, user mengisi email -> bila akun ada dan tidak diblokir, dibuat token acak
   (berlaku 30 menit) dan tautannya dikirim ke email itu. Jawaban API SELALU sama, ada akun atau
   tidak, supaya daftar email terdaftar tidak bisa ditebak dari sini. Maks. 3 permintaan/jam/akun.
2. Jalur cadangan tanpa server email: admin portal membuat tautan untuk akun tertentu dari halaman
   Admin (berlaku 24 jam) lalu mengirimkannya sendiri ke pemilik akun.
3. User membuka tautan, membuat password baru (8-72 byte). Token dipakai sekali; semua token lain
   akun itu ikut gugur dan semua sesi login akun itu diakhiri.

Hanya hash SHA-256 token yang disimpan; token asli hanya ada di tautan. SQL portabel.
"""
from __future__ import annotations

import hashlib
import logging
import os
import secrets
import threading
from datetime import datetime, timedelta
from typing import Any

import bcrypt
from sqlalchemy import text
from sqlalchemy.engine import Engine

from app.services import mailer, sqlcompat

logger = logging.getLogger(__name__)

PORTAL = {
    "akreditasi": {"users": "akreditasi_users", "sessions": "akreditasi_sessions", "nama": "Portal Akreditasi"},
    "dampak": {"users": "dampak_users", "sessions": "dampak_sessions", "nama": "Analisis Dampak"},
}
BERLAKU_EMAIL = timedelta(minutes=30)
BERLAKU_ADMIN = timedelta(hours=24)
MAKS_PER_JAM = 3
JAWABAN_UMUM = ("Jika email itu terdaftar, tautan untuk membuat password baru sudah dikirim ke email tersebut "
                "(berlaku 30 menit). Tidak menerima email? Periksa folder spam, atau minta admin portal "
                "membuatkan tautan reset.")


class ResetError(ValueError):
    """Permintaan tidak valid / tautan tidak berlaku (400)."""


def _portal(portal: str) -> dict[str, str]:
    if portal not in PORTAL:
        raise ResetError("Portal tidak dikenal.")
    return PORTAL[portal]


def _hash_token(token: str) -> str:
    return hashlib.sha256((token or "").encode("utf-8")).hexdigest()


def ensure_schema(engine: Engine) -> None:
    id_clause = {
        "postgresql": "SERIAL PRIMARY KEY",
        "mysql": "INTEGER NOT NULL AUTO_INCREMENT PRIMARY KEY",
        "sqlite": "INTEGER NOT NULL PRIMARY KEY AUTOINCREMENT",
    }.get(engine.dialect.name, "INTEGER NOT NULL PRIMARY KEY")
    with engine.begin() as conn:
        conn.execute(text(f"""
            CREATE TABLE IF NOT EXISTS reset_password_token (
                id {id_clause},
                portal VARCHAR(16) NOT NULL,
                user_id INTEGER NOT NULL,
                token_hash CHAR(64) NOT NULL,
                dibuat_oleh VARCHAR(254),
                created_at TIMESTAMP NOT NULL,
                expires_at TIMESTAMP NOT NULL,
                used_at TIMESTAMP
            )
        """))
    try:
        with engine.begin() as conn:
            conn.execute(text(sqlcompat.index_ddl(engine, "reset_password_token", ["token_hash"],
                                                  name="reset_password_token_hash", unique=True)))
    except Exception as exc:  # noqa: BLE001 -- index sudah ada
        if not sqlcompat.is_duplicate_index_error(exc):
            raise


def _buat_token(conn, portal: str, user_id: int, berlaku: timedelta, oleh: str) -> tuple[str, datetime]:
    token = secrets.token_urlsafe(32)
    now = datetime.now()
    # Tautan baru menggantikan tautan lama yang belum dipakai.
    conn.execute(text("""
        UPDATE reset_password_token SET used_at = :now
        WHERE portal = :p AND user_id = :u AND used_at IS NULL
    """), {"now": now, "p": portal, "u": user_id})
    conn.execute(text("""
        INSERT INTO reset_password_token (portal, user_id, token_hash, dibuat_oleh, created_at, expires_at)
        VALUES (:p, :u, :h, :o, :c, :e)
    """), {"p": portal, "u": user_id, "h": _hash_token(token), "o": oleh, "c": now, "e": now + berlaku})
    return token, now + berlaku


def _kirim_aman(ke: str, subjek: str, isi: str, portal: str) -> None:
    try:
        mailer.kirim(ke, subjek, isi)
    except Exception:  # noqa: BLE001 -- kegagalan SMTP dicatat, tidak dikembalikan ke peminta
        logger.exception("email reset password gagal dikirim (%s)", portal)


def tautan(base_url: str, portal: str, token: str) -> str:
    return f"{base_url.rstrip('/')}/reset-password?portal={portal}&token={token}"


def minta_reset(engine: Engine, portal: str, email: str, base_url: str) -> dict[str, Any]:
    """Kirim tautan reset ke email bila akunnya ada. Jawaban selalu sama (tidak membocorkan akun)."""
    cfg = _portal(portal)
    email = (email or "").strip().lower()
    if not email or len(email) > 254:
        raise ResetError("Isi email akun Anda.")
    with engine.begin() as conn:
        user = conn.execute(text(f"SELECT id, nama, is_blocked FROM {cfg['users']} WHERE email = :e"),
                            {"e": email}).mappings().first()
        if not user or user["is_blocked"]:
            return {"message": JAWABAN_UMUM}
        n = conn.execute(text("""
            SELECT COUNT(*) FROM reset_password_token
            WHERE portal = :p AND user_id = :u AND dibuat_oleh = 'email' AND created_at >= :sejak
        """), {"p": portal, "u": user["id"], "sejak": datetime.now() - timedelta(hours=1)}).scalar() or 0
        if n >= MAKS_PER_JAM:
            return {"message": JAWABAN_UMUM}
        token, sampai = _buat_token(conn, portal, int(user["id"]), BERLAKU_EMAIL, "email")
    link = tautan(base_url, portal, token)
    if mailer.terkonfigurasi():
        # Dikirim di latar: respons tidak menunggu SMTP, jadi lama jawaban tidak membedakan akun ada/tidak.
        isi = (f"Halo {user['nama']},\n\nAda permintaan membuat password baru untuk akun {cfg['nama']} Anda. "
               f"Buka tautan berikut (berlaku sampai {sampai:%d-%m-%Y %H:%M}, sekali pakai):\n\n{link}\n\n"
               "Abaikan email ini bila Anda tidak memintanya; password lama tetap berlaku.\n")
        threading.Thread(target=_kirim_aman, args=(email, f"Reset password {cfg['nama']} UGM Analytics", isi, portal),
                         daemon=True).start()
    elif os.environ.get("RESET_LINK_KE_LOG") == "1":
        # Hanya untuk mode kerja lokal (web/dev_api_mysql.py) saat SMTP belum diisi.
        logger.warning("SMTP belum diatur; tautan reset %s untuk %s: %s", portal, email, link)
    return {"message": JAWABAN_UMUM}


def buat_tautan_admin(engine: Engine, portal: str, admin: dict[str, Any], target_id: int, base_url: str) -> dict[str, Any]:
    """Admin membuat tautan reset untuk akun di portalnya (dikirim sendiri, mis. lewat WA)."""
    cfg = _portal(portal)
    with engine.begin() as conn:
        pelaku = conn.execute(text(f"SELECT is_admin, is_blocked FROM {cfg['users']} WHERE id = :id"),
                              {"id": admin["id"]}).mappings().first()
        if not pelaku or not pelaku["is_admin"] or pelaku["is_blocked"]:
            raise PermissionError("Hanya admin yang boleh membuat tautan reset.")
        target = conn.execute(text(f"SELECT id, email FROM {cfg['users']} WHERE id = :id"),
                              {"id": target_id}).mappings().first()
        if not target:
            raise ResetError("Akun tidak ditemukan.")
        token, sampai = _buat_token(conn, portal, int(target["id"]), BERLAKU_ADMIN, admin["email"])
    return {"email": target["email"], "tautan": tautan(base_url, portal, token), "berlaku_sampai": sampai.isoformat(timespec="minutes"),
            "message": f"Tautan reset untuk {target['email']} dibuat (berlaku 24 jam, sekali pakai). Kirimkan hanya ke pemilik akun."}


def _token_aktif(conn, portal: str, token: str) -> dict[str, Any]:
    cfg = _portal(portal)
    # Kedaluwarsa & sudah-dipakai dicek di SQL: tipe TIMESTAMP yang dikembalikan tiap dialek berbeda.
    row = conn.execute(text("""
        SELECT id, user_id FROM reset_password_token
        WHERE portal = :p AND token_hash = :h AND used_at IS NULL AND expires_at > :now
    """), {"p": portal, "h": _hash_token(token), "now": datetime.now()}).mappings().first()
    if not row:
        raise ResetError("Tautan reset tidak berlaku (salah, sudah dipakai, atau kedaluwarsa). Minta tautan baru.")
    user = conn.execute(text(f"SELECT id, email, nama, is_blocked FROM {cfg['users']} WHERE id = :id"),
                        {"id": row["user_id"]}).mappings().first()
    if not user or user["is_blocked"]:
        raise ResetError("Akun ini tidak aktif.")
    return {"token_id": int(row["id"]), **dict(user)}


def cek(engine: Engine, portal: str, token: str) -> dict[str, Any]:
    with engine.connect() as conn:
        info = _token_aktif(conn, portal, token)
    return {"email": info["email"], "nama": info["nama"], "portal": portal, "nama_portal": PORTAL[portal]["nama"]}


def reset(engine: Engine, portal: str, token: str, password: str) -> dict[str, Any]:
    cfg = _portal(portal)
    if len(password or "") < 8 or len((password or "").encode()) > 72:
        raise ResetError("Password harus 8–72 byte.")
    now = datetime.now()
    with engine.begin() as conn:
        info = _token_aktif(conn, portal, token)
        conn.execute(text(f"UPDATE {cfg['users']} SET password_hash = :h, auth_provider = 'local' WHERE id = :id"),
                     {"h": bcrypt.hashpw(password.encode(), bcrypt.gensalt()).decode(), "id": info["id"]})
        conn.execute(text("""
            UPDATE reset_password_token SET used_at = :now WHERE portal = :p AND user_id = :u AND used_at IS NULL
        """), {"now": now, "p": portal, "u": info["id"]})
        # Password lama mungkin bocor: semua sesi login akun ini diakhiri.
        conn.execute(text(f"DELETE FROM {cfg['sessions']} WHERE user_id = :u"), {"u": info["id"]})
    return {"message": "Password baru tersimpan. Silakan masuk dengan password baru.", "email": info["email"]}
