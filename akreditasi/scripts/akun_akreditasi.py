"""Data akun app akreditasi: riwayat generate laporan, pekerjaan "ongoing" per
user, dan aksi admin (blokir / hapus / jadikan admin).

Semua aksi admin memeriksa ulang dari DB bahwa PELAKU memang admin aktif --
tidak mengandalkan tombol yang disembunyikan di UI. Pelaku tidak boleh
memblokir, menghapus, atau mencabut status admin AKUNNYA SENDIRI, supaya
admin tidak bisa mengunci dirinya keluar dari sistem.
"""

import re
import sys
from datetime import datetime
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

import pandas as pd  # noqa: E402
from sqlalchemy import text  # noqa: E402

import db  # noqa: E402
from auth_akreditasi import ambil_user_aktif, hapus_sesi_user  # noqa: E402
from registry_kebutuhan_data import KEBUTUHAN_DATA, dokumen_dari_item, ringkasan_status  # noqa: E402

GENERATED_DIR = Path(__file__).resolve().parents[1] / "data" / "generated"


# ---------------------------------------------------------------- riwayat generate
def simpan_riwayat_generate(user_email: str, prodi_id: str, jenis_dokumen: str,
                            docx_bytes: bytes) -> None:
    """Simpan file hasil generate ke disk + catat di akreditasi_riwayat_generate.
    Dipanggil setiap kali tombol Generate laporan diklik."""
    stempel = datetime.now()
    aman = re.sub(r"[^A-Za-z0-9_-]", "_", prodi_id)
    folder = GENERATED_DIR / aman
    folder.mkdir(parents=True, exist_ok=True)
    path = folder / f"{stempel:%Y%m%d_%H%M%S_%f}_{jenis_dokumen}.docx"
    path.write_bytes(docx_bytes)
    try:
        with db.get_engine().begin() as conn:
            conn.execute(
                text(f"INSERT INTO `{db.t('riwayat_generate')}` "
                     "(user_email, prodi_id, jenis_dokumen, file_path, generated_at) "
                     "VALUES (:e, :p, :j, :f, :t)"),
                {"e": user_email, "p": prodi_id, "j": jenis_dokumen,
                 "f": str(path), "t": stempel},
            )
    except Exception:
        path.unlink(missing_ok=True)  # jangan tinggalkan file yatim
        raise


def riwayat_generate_user(user_email: str) -> pd.DataFrame:
    return db.read_sql_retry(
        db.get_engine(),
        f"SELECT r.id, r.prodi_id, COALESCE(p.nama, r.prodi_id) AS nama_prodi, "
        f"r.jenis_dokumen, r.file_path, r.generated_at "
        f"FROM `{db.t('riwayat_generate')}` r "
        f"LEFT JOIN `{db.t('prodi')}` p ON p.slug = r.prodi_id "
        f"WHERE r.user_email = :e ORDER BY r.generated_at DESC",
        label="riwayat generate user", params={"e": user_email},
    )


def baca_file_riwayat(file_path: str) -> bytes | None:
    """Isi file riwayat, atau None kalau file sudah tidak ada. Path WAJIB
    berada di dalam GENERATED_DIR (path berasal dari DB, tetap dicek)."""
    path = Path(file_path).resolve()
    if not path.is_relative_to(GENERATED_DIR.resolve()) or not path.is_file():
        return None
    return path.read_bytes()


# ---------------------------------------------------------------- ongoing
def pekerjaan_ongoing(user_email: str) -> list[dict]:
    """Kombinasi (prodi, LED/LKPS) di mana user ini punya >=1 item yang sudah
    ia konfirmasi. Kelengkapan dihitung PERSIS spt progress bar di halaman
    /akreditasi (item terisi oleh siapa pun di prodi itu)."""
    engine = db.get_engine()
    milik = db.read_sql_retry(
        engine,
        f"SELECT DISTINCT prodi_id, item_id FROM `{db.t('data_manual')}` WHERE diisi_oleh = :e",
        label="item milik user", params={"e": user_email},
    )
    kombinasi = {}
    for _, r in milik.iterrows():
        item = KEBUTUHAN_DATA.get(r["item_id"])
        if item:
            kombinasi.setdefault((r["prodi_id"], dokumen_dari_item(item)), 0)
            kombinasi[(r["prodi_id"], dokumen_dari_item(item))] += 1
    if not kombinasi:
        return []

    prodi_ids = sorted({p for p, _ in kombinasi})
    params = {f"p{i}": v for i, v in enumerate(prodi_ids)}
    ph = ", ".join(f":p{i}" for i in range(len(prodi_ids)))
    terisi = db.read_sql_retry(
        engine,
        f"SELECT DISTINCT prodi_id, item_id FROM `{db.t('data_manual')}` WHERE prodi_id IN ({ph})",
        label="item terisi per prodi", params=params,
    )
    info = db.read_sql_retry(
        engine,
        f"SELECT p.slug, p.nama AS nama_prodi, f.nama AS nama_fakultas "
        f"FROM `{db.t('prodi')}` p LEFT JOIN `{db.t('fakultas')}` f ON f.id = p.fakultas_id "
        f"WHERE p.slug IN ({ph})",
        label="info prodi", params=params,
    ).set_index("slug")

    hasil = []
    for (prodi_id, dokumen), n_milik in sorted(kombinasi.items()):
        item_ids = [k for k, v in KEBUTUHAN_DATA.items() if dokumen_dari_item(v) == dokumen]
        terisi_ids = set(terisi.loc[terisi["prodi_id"] == prodi_id, "item_id"])
        ring = ringkasan_status(item_ids=item_ids, terisi_ids=terisi_ids)
        hasil.append({
            "prodi_id": prodi_id,
            "nama_prodi": info["nama_prodi"].get(prodi_id, prodi_id),
            "nama_fakultas": info["nama_fakultas"].get(prodi_id),
            "dokumen": dokumen,
            "ringkasan": ring,
            "item_milik_user": n_milik,
        })
    return hasil


# ---------------------------------------------------------------- admin
def daftar_user() -> pd.DataFrame:
    """Semua user + jumlah dokumen yang pernah mereka generate."""
    return db.read_sql_retry(
        db.get_engine(),
        f"SELECT u.id, u.nama, u.email, u.created_at, u.last_login_at, u.is_admin, u.is_blocked, "
        f"  (SELECT COUNT(*) FROM `{db.t('riwayat_generate')}` r "
        f"     WHERE r.user_email = u.email) AS n_generate "
        f"FROM `{db.t('users')}` u ORDER BY u.id",
        label="daftar user",
    )


class AksiDitolak(Exception):
    pass


def _cek_pelaku(pelaku_id: int, target_id: int, aksi: str) -> None:
    pelaku = ambil_user_aktif(pelaku_id)
    if not pelaku or not pelaku["is_admin"]:
        raise AksiDitolak("Hanya admin yang boleh melakukan aksi ini.")
    if pelaku_id == target_id:
        raise AksiDitolak(f"Anda tidak boleh {aksi} akun Anda sendiri.")


def set_blokir(pelaku_id: int, target_id: int, blokir: bool) -> None:
    _cek_pelaku(pelaku_id, target_id, "memblokir" if blokir else "membuka blokir")
    with db.get_engine().begin() as conn:
        conn.execute(text(f"UPDATE `{db.t('users')}` SET is_blocked = :b WHERE id = :id"),
                     {"b": int(blokir), "id": target_id})
        if blokir:
            hapus_sesi_user(conn, target_id)


def set_admin(pelaku_id: int, target_id: int, admin: bool) -> None:
    _cek_pelaku(pelaku_id, target_id, "mengubah status admin")
    with db.get_engine().begin() as conn:
        conn.execute(text(f"UPDATE `{db.t('users')}` SET is_admin = :a WHERE id = :id"),
                     {"a": int(admin), "id": target_id})


def hapus_user(pelaku_id: int, target_id: int) -> None:
    """Hapus akun + sesi + riwayat generate-nya (termasuk file). Data yang ia
    konfirmasi di akreditasi_data_manual SENGAJA DIBIARKAN -- itu data resmi
    prodi, bukan milik pribadi akun."""
    _cek_pelaku(pelaku_id, target_id, "menghapus")
    engine = db.get_engine()
    with engine.connect() as conn:
        email = conn.execute(text(f"SELECT email FROM `{db.t('users')}` WHERE id = :id"),
                             {"id": target_id}).scalar()
    if email is None:
        return
    files = riwayat_generate_user(email)["file_path"].tolist()
    with engine.begin() as conn:
        hapus_sesi_user(conn, target_id)
        conn.execute(text(f"DELETE FROM `{db.t('riwayat_generate')}` WHERE user_email = :e"),
                     {"e": email})
        conn.execute(text(f"DELETE FROM `{db.t('login_attempts')}` WHERE email = :e"),
                     {"e": email})
        conn.execute(text(f"DELETE FROM `{db.t('users')}` WHERE id = :id"), {"id": target_id})
    for f in files:
        path = Path(f).resolve()
        if path.is_relative_to(GENERATED_DIR.resolve()):
            path.unlink(missing_ok=True)
