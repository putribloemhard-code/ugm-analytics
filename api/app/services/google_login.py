"""Masuk dengan Google (OAuth 2.0 / OpenID Connect) untuk dua portal, di samping login password.

Alur (authorization code + PKCE, sisi server):
1. `/auth/google/start?portal=...` -> buat `state`, `nonce`, dan PKCE verifier acak, simpan di cookie
   httponly berumur 10 menit, lalu arahkan browser ke Google.
2. Google kembali ke `/auth/google/callback?code&state`. `state` wajib sama dengan cookie, `code`
   ditukar di token endpoint Google (langsung server-ke-server lewat TLS, jadi isi id_token boleh
   dipercaya tanpa cek tanda tangan -- OIDC Core 3.1.3.7), lalu klaimnya diperiksa: iss, aud,
   exp, nonce, email_verified, dan domain email UGM.
3. Email dicocokkan ke akun portal itu. Akun lama (daftar password) tetap dipakai apa adanya --
   status admin & datanya tidak berubah. Email UGM yang belum punya akun dibuatkan otomatis
   (auth_provider 'google', tanpa password; akun pertama portal tetap jadi admin).
4. Sesi login dibuat persis seperti login password (token acak, hash di tabel sesi, 12 jam).

Konfigurasi dari env: GOOGLE_CLIENT_ID + GOOGLE_CLIENT_SECRET, atau GOOGLE_CLIENT_SECRET_FILE
(file JSON unduhan Google Cloud Console). GOOGLE_REDIRECT_URI opsional untuk menimpa alamat callback.
Tanpa konfigurasi, tombol Google tidak ditampilkan dan login password berjalan seperti biasa.
"""
from __future__ import annotations

import base64
import hashlib
import json
import os
import secrets
import time
from datetime import datetime
from typing import Any, Callable
from urllib.parse import urlencode

from sqlalchemy import text
from sqlalchemy.engine import Engine

from app.services import accreditation_auth, dampak_auth, sqlcompat

AUTH_URL = "https://accounts.google.com/o/oauth2/v2/auth"
TOKEN_URL = "https://oauth2.googleapis.com/token"
ISSUER = {"accounts.google.com", "https://accounts.google.com"}
STATE_COOKIE = "google_oauth"
STATE_AGE = 600  # detik
CALLBACK_PATH = "/api/v1/analytics/auth/google/callback"

PORTAL = {
    "akreditasi": {"users": "akreditasi_users", "sessions": "akreditasi_sessions", "auth": accreditation_auth,
                   "path": "/akreditasi"},
    "dampak": {"users": "dampak_users", "sessions": "dampak_sessions", "auth": dampak_auth, "path": "/dampak"},
}


class GoogleLoginError(ValueError):
    """Login Google ditolak; pesannya aman ditampilkan ke pengguna."""


def konfigurasi() -> dict[str, str] | None:
    client_id = os.environ.get("GOOGLE_CLIENT_ID", "").strip()
    secret = os.environ.get("GOOGLE_CLIENT_SECRET", "").strip()
    berkas = os.environ.get("GOOGLE_CLIENT_SECRET_FILE", "").strip()
    if berkas and not (client_id and secret):
        try:
            with open(berkas, encoding="utf-8") as f:
                data = json.load(f)
            web = data.get("web") or data.get("installed") or {}
            client_id = client_id or web.get("client_id", "")
            secret = secret or web.get("client_secret", "")
        except (OSError, ValueError):
            return None
    if not client_id or not secret:
        return None
    return {"client_id": client_id, "client_secret": secret}


def aktif() -> bool:
    return konfigurasi() is not None


def redirect_uri(base_url: str) -> str:
    return os.environ.get("GOOGLE_REDIRECT_URI", "").strip() or base_url.rstrip("/") + CALLBACK_PATH


def tujuan_aman(portal: str, tujuan: str) -> bool:
    """Halaman kembali setelah login: hanya path di dalam portal itu sendiri (bukan open redirect)."""
    dasar = PORTAL.get(portal, {}).get("path")
    if not dasar or not tujuan or "//" in tujuan or "\\" in tujuan or "\r" in tujuan or "\n" in tujuan:
        return False
    return tujuan == dasar or tujuan.startswith((dasar + "/", dasar + "?"))


def _b64url(data: bytes) -> str:
    return base64.urlsafe_b64encode(data).rstrip(b"=").decode("ascii")


def mulai(portal: str, redirect: str) -> tuple[str, str]:
    """-> (URL Google tujuan, nilai cookie state)."""
    if portal not in PORTAL:
        raise GoogleLoginError("Portal tidak dikenal.")
    cfg = konfigurasi()
    if not cfg:
        raise GoogleLoginError("Login Google belum diaktifkan di server ini.")
    state, nonce, verifier = secrets.token_urlsafe(24), secrets.token_urlsafe(24), secrets.token_urlsafe(48)
    url = AUTH_URL + "?" + urlencode({
        "client_id": cfg["client_id"],
        "redirect_uri": redirect,
        "response_type": "code",
        "scope": "openid email profile",
        "state": state,
        "nonce": nonce,
        "code_challenge": _b64url(hashlib.sha256(verifier.encode("ascii")).digest()),
        "code_challenge_method": "S256",
        "prompt": "select_account",
    })
    return url, ".".join((portal, state, nonce, verifier))


def baca_cookie(nilai: str | None) -> dict[str, str] | None:
    bagian = (nilai or "").split(".")
    if len(bagian) != 4 or bagian[0] not in PORTAL:
        return None
    return dict(zip(("portal", "state", "nonce", "verifier"), bagian))


def _tukar_code(cfg: dict[str, str], code: str, verifier: str, redirect: str) -> dict[str, Any]:
    import httpx
    resp = httpx.post(TOKEN_URL, timeout=15, data={
        "code": code, "client_id": cfg["client_id"], "client_secret": cfg["client_secret"],
        "redirect_uri": redirect, "grant_type": "authorization_code", "code_verifier": verifier,
    })
    if resp.status_code != 200:
        raise GoogleLoginError("Google menolak permintaan login. Coba lagi.")
    return resp.json()


def _klaim_id_token(id_token: str) -> dict[str, Any]:
    try:
        payload = id_token.split(".")[1]
        return json.loads(base64.urlsafe_b64decode(payload + "=" * (-len(payload) % 4)))
    except (IndexError, ValueError) as exc:
        raise GoogleLoginError("Jawaban Google tidak dapat dibaca.") from exc


def periksa_klaim(klaim: dict[str, Any], client_id: str, nonce: str) -> dict[str, str]:
    if klaim.get("iss") not in ISSUER or klaim.get("aud") != client_id:
        raise GoogleLoginError("Token Google tidak ditujukan untuk aplikasi ini.")
    if float(klaim.get("exp") or 0) < time.time():
        raise GoogleLoginError("Sesi login Google kedaluwarsa. Coba lagi.")
    if not nonce or klaim.get("nonce") != nonce:
        raise GoogleLoginError("Sesi login Google tidak cocok. Coba lagi.")
    email = accreditation_auth.normalize_email(str(klaim.get("email") or ""))
    if klaim.get("email_verified") not in (True, "true"):
        raise GoogleLoginError("Email akun Google ini belum terverifikasi.")
    if not accreditation_auth.valid_email(email):
        raise GoogleLoginError(f"Akun {email or 'ini'} bukan email UGM. Pilih akun @ugm.ac.id atau @mail.ugm.ac.id.")
    nama = (str(klaim.get("name") or "").strip() or email.split("@")[0])[:100]
    return {"email": email, "nama": nama}


def masuk(engine: Engine, portal: str, email: str, nama: str) -> tuple[dict[str, Any], str]:
    """Cari/buat akun portal untuk email Google ini lalu buat sesi. -> (user, token sesi)."""
    cfg = PORTAL[portal]
    auth = cfg["auth"]
    users, sessions = cfg["users"], cfg["sessions"]
    now = datetime.now()
    pilih = f"SELECT id, email, nama, is_admin, is_blocked FROM {users} WHERE email = :e"
    with engine.begin() as conn:
        row = conn.execute(text(pilih), {"e": email}).mappings().first()
        if not row:
            try:
                conn.execute(text(f"""
                    INSERT INTO {users} (email, nama, password_hash, auth_provider, is_admin, is_blocked, created_at)
                    VALUES (:e, :n, NULL, 'google', FALSE, FALSE, :now)
                """), {"e": email, "n": nama, "now": now})
            except Exception as exc:  # noqa: BLE001 -- dua tab login bersamaan: akun sudah dibuat tab lain
                if not sqlcompat.is_duplicate_entry_error(exc):
                    raise
            row = conn.execute(text(pilih), {"e": email}).mappings().first()
            # Akun pertama portal jadi admin -- sama dengan register() biasa.
            if conn.execute(text(f"SELECT MIN(id) FROM {users}")).scalar() == row["id"] and not row["is_admin"]:
                conn.execute(text(f"UPDATE {users} SET is_admin = TRUE WHERE id = :id"), {"id": row["id"]})
                row = conn.execute(text(pilih), {"e": email}).mappings().first()
        if row["is_blocked"]:
            raise GoogleLoginError("Akun Anda diblokir, hubungi admin.")
        token = secrets.token_urlsafe(32)
        conn.execute(text(f"DELETE FROM {sessions} WHERE expires_at < :now"), {"now": now})
        conn.execute(text(f"""
            INSERT INTO {sessions} (token_hash, user_id, created_at, expires_at)
            VALUES (:hash, :user_id, :created, :expires)
        """), {"hash": auth.token_hash(token), "user_id": row["id"], "created": now, "expires": now + auth.SESSION_AGE})
        conn.execute(text(f"UPDATE {users} SET last_login_at = :now WHERE id = :id"), {"now": now, "id": row["id"]})
    return {"id": row["id"], "email": row["email"], "nama": row["nama"], "is_admin": bool(row["is_admin"])}, token


def selesaikan(engine: Engine, code: str, state: str, cookie: dict[str, str] | None, redirect: str,
               tukar: Callable[..., dict[str, Any]] = _tukar_code) -> tuple[str, dict[str, Any], str]:
    """Callback Google -> (portal, user, token sesi). `tukar` bisa diganti di pengujian."""
    if not cookie or not state or not secrets.compare_digest(cookie["state"], state):
        raise GoogleLoginError("Sesi login Google tidak cocok atau sudah lewat 10 menit. Coba lagi.")
    cfg = konfigurasi()
    if not cfg:
        raise GoogleLoginError("Login Google belum diaktifkan di server ini.")
    if not code:
        raise GoogleLoginError("Login Google dibatalkan.")
    jawaban = tukar(cfg, code, cookie["verifier"], redirect)
    akun = periksa_klaim(_klaim_id_token(str(jawaban.get("id_token") or "")), cfg["client_id"], cookie["nonce"])
    user, token = masuk(engine, cookie["portal"], akun["email"], akun["nama"])
    return cookie["portal"], user, token
