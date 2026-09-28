"""Halaman Admin portal Analisis Dampak: daftar akun + blokir / status admin / hapus.

Padanan AccreditationAccountService.admin_* untuk tabel dampak_users (akun Dampak terpisah
dari akun Akreditasi). Hak admin dicek ULANG dari basis data, bukan dari klaim sesi.
"""
from __future__ import annotations

from typing import Any

from sqlalchemy import text
from sqlalchemy.engine import Engine

from app.services.accreditation_account import AksiDitolak, _iso, _tanggal

# Tag manual yang disimpan akun Dampak (kolom `oleh` = email); tabel bisa belum ada.
TABEL_TAG = ("berita_sdg_manual", "berita_tema_manual")


class DampakAccountService:
    def __init__(self, engine: Engine):
        self.engine = engine

    def _pastikan_admin(self, user: dict[str, Any]) -> None:
        with self.engine.connect() as conn:
            row = conn.execute(text("SELECT is_admin, is_blocked FROM dampak_users WHERE id = :id"),
                               {"id": user["id"]}).mappings().first()
        if not row or not row["is_admin"] or row["is_blocked"]:
            raise AksiDitolak("Hanya admin Analisis Dampak yang boleh melakukan aksi ini.")

    def _jumlah_tag(self, conn) -> dict[str, int]:
        jumlah: dict[str, int] = {}
        for tabel in TABEL_TAG:
            try:
                with conn.begin_nested():
                    for email, n in conn.execute(text(f"SELECT oleh, COUNT(DISTINCT url) FROM {tabel} GROUP BY oleh")):
                        jumlah[email] = jumlah.get(email, 0) + int(n)
            except Exception:  # noqa: BLE001 -- tabel tag belum dibuat
                continue
        return jumlah

    def admin_overview(self, user: dict[str, Any]) -> dict[str, Any]:
        self._pastikan_admin(user)
        with self.engine.connect() as conn:
            rows = conn.execute(text(
                "SELECT id, nama, email, created_at, last_login_at, is_admin, is_blocked FROM dampak_users ORDER BY id"
            )).mappings().all()
            tag = self._jumlah_tag(conn)
        users = [{
            "id": row["id"], "nama": row["nama"], "email": row["email"],
            "is_admin": bool(row["is_admin"]), "is_blocked": bool(row["is_blocked"]),
            "terdaftar": _tanggal(row["created_at"]), "login_terakhir": _tanggal(row["last_login_at"]),
            "created_at": _iso(row["created_at"]), "last_login_at": _iso(row["last_login_at"]),
            "n_tag": tag.get(row["email"], 0),
            "diri_sendiri": int(row["id"]) == int(user["id"]),
        } for row in rows]
        return {
            "summary": {"total_akun": len(users), "admin": sum(u["is_admin"] for u in users),
                        "diblokir": sum(u["is_blocked"] for u in users)},
            "users": users,
        }

    def admin_action(self, pelaku: dict[str, Any], action: str, target_id: int, value: bool | None = None) -> dict[str, Any]:
        self._pastikan_admin(pelaku)
        if int(pelaku["id"]) == int(target_id):
            raise AksiDitolak("Aksi ini tidak berlaku untuk akun Anda sendiri.")
        with self.engine.connect() as conn:
            target = conn.execute(text("SELECT id, email FROM dampak_users WHERE id = :id"), {"id": target_id}).mappings().first()
        if not target:
            raise AksiDitolak("Akun tujuan tidak ditemukan.")
        with self.engine.begin() as conn:
            if action == "blokir":
                conn.execute(text("UPDATE dampak_users SET is_blocked = :b WHERE id = :id"), {"b": bool(value), "id": target_id})
                if value:
                    conn.execute(text("DELETE FROM dampak_sessions WHERE user_id = :id"), {"id": target_id})
                pesan = f"Blokir {target['email']} {'dipasang' if value else 'dibuka'}."
            elif action == "admin":
                conn.execute(text("UPDATE dampak_users SET is_admin = :a WHERE id = :id"), {"a": bool(value), "id": target_id})
                pesan = f"Status admin {target['email']} {'diberikan' if value else 'dicabut'}."
            elif action == "hapus":
                # Tag manual yang pernah ia simpan tetap ada: itu data analisis, bukan milik akun.
                conn.execute(text("DELETE FROM dampak_sessions WHERE user_id = :id"), {"id": target_id})
                conn.execute(text("DELETE FROM dampak_users WHERE id = :id"), {"id": target_id})
                pesan = f"Akun {target['email']} dihapus."
            else:
                raise AksiDitolak(f"Aksi tidak dikenal: {action}")
        return {"message": pesan, "email": target["email"], "action": action}
