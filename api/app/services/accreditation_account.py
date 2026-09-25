"""Profil akun & kelola akun akreditasi untuk API -- padanan page_profil.py + page_admin.py
dashboard Streamlit lama (akreditasi/scripts/akun_akreditasi.py, page_profil.py, page_admin.py).

Perbedaan penting dari versi Streamlit:
- Semua aksi admin dicek ULANG di sini dari DB (pelaku harus admin aktif, bukan akun sendiri),
  jadi tidak bergantung pada tombol yang disembunyikan di UI. Sama seperti akun_akreditasi.py.
- Tidak ada hapus file di disk: file laporan ada di mesin ini, bukan di server API (di produksi
  keduanya satu container, tapi menghapus berkas dari API bukan tugasnya).
"""
from __future__ import annotations

from datetime import datetime
from typing import Any

from sqlalchemy import text
from sqlalchemy.engine import Engine

from app.domain.source import load_accreditation_module
from app.services import accreditation_sumber as sumber


class AksiDitolak(Exception):
    """Aksi admin ditolak (bukan admin / target akun sendiri / target tidak ada)."""


def _pct(ringkasan: dict[str, Any]) -> int:
    total = int(ringkasan.get("total") or 0)
    return round(int(ringkasan.get("lengkap") or 0) / total * 100) if total else 0


def _sebagai_datetime(nilai: Any) -> datetime | None:
    """Terima objek datetime (MySQL/Postgres) maupun string ISO (SQLite) -> datetime."""
    if isinstance(nilai, datetime):
        return nilai
    if isinstance(nilai, str) and nilai.strip():
        try:
            return datetime.fromisoformat(nilai.strip().replace("Z", "+00:00"))
        except ValueError:
            return None
    return None


def _iso(nilai: Any) -> str | None:
    waktu = _sebagai_datetime(nilai)
    return waktu.isoformat() if waktu else (str(nilai) if nilai else None)


def _tanggal(nilai: Any) -> str | None:
    """Format tampilan ala dashboard lama: '18 Sep 2026, 09:17'."""
    waktu = _sebagai_datetime(nilai)
    if not waktu:
        return str(nilai) if nilai else None
    bulan = ["Jan", "Feb", "Mar", "Apr", "Mei", "Jun", "Jul", "Agu", "Sep", "Okt", "Nov", "Des"]
    return f"{waktu.day:02d} {bulan[waktu.month - 1]} {waktu.year}, {waktu:%H:%M}"


class AccreditationAccountService:
    """Baca profil satu user + kelola akun (khusus admin)."""

    def __init__(self, engine: Engine):
        self.engine = engine

    # ------------------------------------------------------------------ profil
    def profile(self, user: dict[str, Any]) -> dict[str, Any]:
        email = user["email"]
        with self.engine.connect() as conn:
            identitas = conn.execute(text(
                "SELECT created_at, last_login_at FROM akreditasi_users WHERE id = :id"
            ), {"id": user["id"]}).mappings().first()
            n_generate = conn.execute(text(
                "SELECT COUNT(*) FROM akreditasi_riwayat_generate WHERE user_email = :e"
            ), {"e": email}).scalar() or 0
            n_upload = conn.execute(text(
                "SELECT COUNT(*) FROM akreditasi_upload_file WHERE diupload_oleh = :e"
            ), {"e": email}).scalar() or 0
        return {
            "user": {
                "id": user["id"], "email": email, "nama": user["nama"],
                "is_admin": bool(user.get("is_admin")),
                "created_at": _iso(identitas["created_at"]) if identitas else None,
                "last_login_at": _iso(identitas["last_login_at"]) if identitas else None,
                "terdaftar": _tanggal(identitas["created_at"]) if identitas else None,
                "login_terakhir": _tanggal(identitas["last_login_at"]) if identitas else None,
            },
            "stats": {"dokumen_digenerate": int(n_generate), "dokumen_diupload": int(n_upload)},
            "ongoing": self._ongoing(email),
            "riwayat": self._riwayat(email),
        }

    def _ongoing(self, email: str) -> list[dict[str, Any]]:
        """(prodi, LED/LKPS) di mana user ini sudah mengonfirmasi >=1 item.

        Kelengkapan dihitung persis seperti progress bar /akreditasi: item yang terisi oleh
        siapa pun di prodi itu, bukan hanya oleh user ini (lihat page_profil.py).
        """
        registry = load_accreditation_module("registry_kebutuhan_data.py")
        with self.engine.connect() as conn:
            milik = conn.execute(text(
                "SELECT DISTINCT prodi_id, item_id FROM akreditasi_data_manual WHERE diisi_oleh = :e"
            ), {"e": email}).all()
            if not milik:
                return []
            kombinasi: dict[tuple[str, str], int] = {}
            for prodi_id, item_id in milik:
                item = registry.KEBUTUHAN_DATA.get(item_id)
                if item:
                    kunci = (prodi_id, registry.dokumen_dari_item(item))
                    kombinasi[kunci] = kombinasi.get(kunci, 0) + 1
            prodi_ids = sorted({prodi for prodi, _ in kombinasi})
            params = {f"p{i}": value for i, value in enumerate(prodi_ids)}
            placeholders = ", ".join(f":p{i}" for i in range(len(prodi_ids)))
            terisi = conn.execute(text(
                f"SELECT DISTINCT prodi_id, item_id FROM akreditasi_data_manual "
                f"WHERE prodi_id IN ({placeholders})"
            ), params).all()
            # Data live (pipeline Fase 2) ikut dihitung lengkap, sama dengan ruang kerja.
            live_ids = {prodi: set(sumber.data_live(conn, prodi)["items"]) for prodi in prodi_ids}
            info = {
                row["slug"]: row for row in conn.execute(text(
                    f"SELECT p.slug, p.nama AS nama_prodi, f.nama AS nama_fakultas "
                    f"FROM akreditasi_prodi p LEFT JOIN akreditasi_fakultas f ON f.id = p.fakultas_id "
                    f"WHERE p.slug IN ({placeholders})"
                ), params).mappings()
            }

        hasil = []
        for (prodi_id, dokumen), n_milik in sorted(kombinasi.items()):
            item_ids = [k for k, v in registry.KEBUTUHAN_DATA.items()
                        if registry.dokumen_dari_item(v) == dokumen]
            terisi_ids = {item_id for prodi, item_id in terisi if prodi == prodi_id}
            ringkasan = sumber.ringkasan(item_ids, terisi_ids, live_ids.get(prodi_id, set()))
            baris = info.get(prodi_id)
            hasil.append({
                "prodi_id": prodi_id,
                "nama_prodi": (baris["nama_prodi"] if baris else prodi_id) or prodi_id,
                "nama_fakultas": baris["nama_fakultas"] if baris else None,
                "dokumen": dokumen,
                "item_milik_user": n_milik,
                "lengkap": int(ringkasan["lengkap"]),
                "total": int(ringkasan["total"]),
                "persen": _pct(ringkasan),
            })
        return hasil

    def _riwayat(self, email: str, batas: int = 50) -> dict[str, Any]:
        with self.engine.connect() as conn:
            total = conn.execute(text(
                "SELECT COUNT(*) FROM akreditasi_riwayat_generate WHERE user_email = :e"
            ), {"e": email}).scalar() or 0
            rows = conn.execute(text(
                "SELECT r.id, r.prodi_id, COALESCE(p.nama, r.prodi_id) AS nama_prodi, "
                "r.jenis_dokumen, r.generated_at "
                "FROM akreditasi_riwayat_generate r "
                "LEFT JOIN akreditasi_prodi p ON p.slug = r.prodi_id "
                "WHERE r.user_email = :e ORDER BY r.generated_at DESC LIMIT :n"
            ), {"e": email, "n": batas}).mappings().all()
        return {
            "total": int(total),
            "batas": batas,
            "rows": [{
                "id": row["id"], "prodi_id": row["prodi_id"], "nama_prodi": row["nama_prodi"],
                "jenis_dokumen": row["jenis_dokumen"], "generated_at": _iso(row["generated_at"]),
                "digenerate": _tanggal(row["generated_at"]),
            } for row in rows],
        }

    # ------------------------------------------------------------------- admin
    def _pastikan_admin(self, user: dict[str, Any]) -> None:
        """Cek ULANG dari DB: pelaku harus admin aktif (bukan hanya percaya klaim cookie)."""
        with self.engine.connect() as conn:
            row = conn.execute(text(
                "SELECT is_admin, is_blocked FROM akreditasi_users WHERE id = :id"
            ), {"id": user["id"]}).mappings().first()
        if not row or not row["is_admin"] or row["is_blocked"]:
            raise AksiDitolak("Hanya admin yang boleh melakukan aksi ini.")

    def _pastikan_bukan_diri(self, pelaku: dict[str, Any], target_id: int, aksi: str) -> None:
        if int(pelaku["id"]) == int(target_id):
            raise AksiDitolak(f"Anda tidak boleh {aksi} akun Anda sendiri.")

    def admin_overview(self, user: dict[str, Any]) -> dict[str, Any]:
        self._pastikan_admin(user)
        with self.engine.connect() as conn:
            rows = conn.execute(text(
                "SELECT u.id, u.nama, u.email, u.created_at, u.last_login_at, u.is_admin, u.is_blocked, "
                "  (SELECT COUNT(*) FROM akreditasi_riwayat_generate r WHERE r.user_email = u.email) AS n_generate "
                "FROM akreditasi_users u ORDER BY u.id"
            )).mappings().all()
        users = [{
            "id": row["id"], "nama": row["nama"], "email": row["email"],
            "is_admin": bool(row["is_admin"]), "is_blocked": bool(row["is_blocked"]),
            "created_at": _iso(row["created_at"]), "last_login_at": _iso(row["last_login_at"]),
            "terdaftar": _tanggal(row["created_at"]), "login_terakhir": _tanggal(row["last_login_at"]),
            "n_generate": int(row["n_generate"] or 0),
            "diri_sendiri": int(row["id"]) == int(user["id"]),
        } for row in rows]
        return {
            "summary": {
                "total_akun": len(users),
                "admin": sum(1 for u in users if u["is_admin"]),
                "diblokir": sum(1 for u in users if u["is_blocked"]),
            },
            "users": users,
        }

    def _ambil_target(self, conn, target_id: int) -> dict[str, Any] | None:
        return conn.execute(text(
            "SELECT id, email, is_admin, is_blocked FROM akreditasi_users WHERE id = :id"
        ), {"id": target_id}).mappings().first()

    def admin_action(self, pelaku: dict[str, Any], action: str, target_id: int,
                     value: bool | None = None) -> dict[str, Any]:
        self._pastikan_admin(pelaku)
        aksi = {"blokir": "memblokir", "admin": "mengubah status admin",
                "hapus": "menghapus"}.get(action, "mengubah")
        self._pastikan_bukan_diri(pelaku, target_id, aksi)

        with self.engine.connect() as conn:
            target = self._ambil_target(conn, target_id)
        if not target:
            raise AksiDitolak("Akun tujuan tidak ditemukan.")

        if action == "blokir":
            with self.engine.begin() as conn:
                conn.execute(text("UPDATE akreditasi_users SET is_blocked = :b WHERE id = :id"),
                             {"b": int(bool(value)), "id": target_id})
                if value:
                    conn.execute(text("DELETE FROM akreditasi_sessions WHERE user_id = :id"),
                                 {"id": target_id})
            pesan = f"Blokir {target['email']} {'dipasang' if value else 'dibuka'}."
        elif action == "admin":
            with self.engine.begin() as conn:
                conn.execute(text("UPDATE akreditasi_users SET is_admin = :a WHERE id = :id"),
                             {"a": int(bool(value)), "id": target_id})
            pesan = f"Status admin {target['email']} {'diberikan' if value else 'dicabut'}."
        elif action == "hapus":
            # Sesi, riwayat, dan percobaan login ikut terhapus. Data yang ia konfirmasi di
            # akreditasi_data_manual SENGAJA dibiarkan -- itu data resmi prodi, bukan milik akun.
            with self.engine.begin() as conn:
                conn.execute(text("DELETE FROM akreditasi_sessions WHERE user_id = :id"), {"id": target_id})
                conn.execute(text("DELETE FROM akreditasi_riwayat_generate WHERE user_email = :e"),
                             {"e": target["email"]})
                conn.execute(text("DELETE FROM akreditasi_login_attempts WHERE email = :e"),
                             {"e": target["email"]})
                conn.execute(text("DELETE FROM akreditasi_users WHERE id = :id"), {"id": target_id})
            pesan = f"Akun {target['email']} dihapus."
        else:
            raise AksiDitolak(f"Aksi tidak dikenal: {action}")

        return {"message": pesan, "email": target["email"], "action": action,
                "value": None if value is None else bool(value)}
