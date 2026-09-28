"""Kirim email lewat SMTP (opsional). Dipakai tautan reset password.

Aktif bila SMTP_HOST dan SMTP_FROM terisi (lokal: .env di root repo; server: deploy/smtp.env).
Tanpa itu `terkonfigurasi()` False dan pemanggil memakai jalur cadangan (admin membuat tautan).
"""
from __future__ import annotations

import os
import smtplib
import ssl
from email.message import EmailMessage


def terkonfigurasi() -> bool:
    return bool(os.environ.get("SMTP_HOST") and os.environ.get("SMTP_FROM"))


def kirim(ke: str, subjek: str, isi: str) -> None:
    """Kirim email teks biasa. SMTP_SECURITY: "starttls" (bawaan, port 587), "ssl" (465), atau "none"."""
    host = os.environ["SMTP_HOST"]
    port = int(os.environ.get("SMTP_PORT") or 587)
    keamanan = (os.environ.get("SMTP_SECURITY") or "starttls").lower()
    pesan = EmailMessage()
    pesan["From"] = os.environ["SMTP_FROM"]
    pesan["To"] = ke
    pesan["Subject"] = subjek
    pesan.set_content(isi)
    konteks = ssl.create_default_context()
    kelas = smtplib.SMTP_SSL if keamanan == "ssl" else smtplib.SMTP
    kwargs = {"context": konteks} if keamanan == "ssl" else {}
    with kelas(host, port, timeout=20, **kwargs) as smtp:
        if keamanan == "starttls":
            smtp.starttls(context=konteks)
        user, sandi = os.environ.get("SMTP_USER"), os.environ.get("SMTP_PASSWORD")
        if user:
            smtp.login(user, sandi or "")
        smtp.send_message(pesan)
