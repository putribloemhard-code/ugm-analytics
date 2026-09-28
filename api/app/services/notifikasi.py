"""Email pemberitahuan ke admin portal dan email uji SMTP dari halaman Admin.

Semua pengiriman memakai `mailer` dan hanya jalan bila SMTP sudah diatur (deploy/smtp.env).
Pemberitahuan dikirim di latar supaya aksi pengguna tidak menunggu SMTP; kegagalannya hanya dicatat.
"""
from __future__ import annotations

import logging
import threading

from sqlalchemy import text
from sqlalchemy.engine import Engine

from app.services import mailer

logger = logging.getLogger(__name__)
TABEL_USER = {"akreditasi": "akreditasi_users", "dampak": "dampak_users"}
NAMA_PORTAL = {"akreditasi": "Portal Akreditasi", "dampak": "Analisis Dampak"}


def _kirim_semua(tujuan: list[str], subjek: str, isi: str) -> None:
    for ke in tujuan:
        try:
            mailer.kirim(ke, subjek, isi)
        except Exception:  # noqa: BLE001 -- satu alamat gagal tidak menghentikan yang lain
            logger.exception("pemberitahuan admin gagal dikirim ke %s", ke)


def kabari_admin(engine: Engine, portal: str, subjek: str, isi: str) -> int:
    """Kirim email ke semua admin aktif portal ini. -> jumlah penerima (0 bila SMTP belum diatur)."""
    if not mailer.terkonfigurasi():
        return 0
    with engine.connect() as conn:
        tujuan = [r[0] for r in conn.execute(text(
            f"SELECT email FROM {TABEL_USER[portal]} WHERE is_admin = TRUE AND is_blocked = FALSE"))]
    if tujuan:
        threading.Thread(target=_kirim_semua, args=(tujuan, subjek, isi), daemon=True).start()
    return len(tujuan)


def email_uji(portal: str, ke: str) -> dict[str, object]:
    """Kirim satu email uji ke alamat admin sendiri; dijalankan langsung supaya galat SMTP terlihat."""
    if not mailer.terkonfigurasi():
        return {"terkirim": False, "message": "Server email belum diatur. Isi SMTP_HOST dan SMTP_FROM di deploy/smtp.env "
                                              "(contoh: deploy/smtp.env.example), lalu jalankan ulang API."}
    try:
        mailer.kirim(ke, f"Email uji {NAMA_PORTAL[portal]} UGM Analytics",
                     "Email ini dikirim dari halaman Admin untuk memastikan pengaturan server email sudah benar.\n"
                     "Kalau Anda menerimanya, email lupa password dan pemberitahuan admin akan terkirim.\n")
    except Exception as exc:  # noqa: BLE001 -- tampilkan jenis galatnya ke admin, detail di log
        logger.exception("email uji gagal")
        return {"terkirim": False, "message": f"Email uji gagal dikirim ({type(exc).__name__}). Periksa SMTP_HOST, "
                                              "SMTP_PORT, SMTP_SECURITY, SMTP_USER, dan SMTP_PASSWORD."}
    return {"terkirim": True, "message": f"Email uji terkirim ke {ke}. Periksa kotak masuk (dan folder spam)."}
