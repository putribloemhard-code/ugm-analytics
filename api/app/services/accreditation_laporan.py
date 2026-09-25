"""Laporan akreditasi per prodi + tahun, dikunci satu PIN per prodi.

Aturan (disepakati dengan pengguna 2026-09-25):

- Satu laporan = prodi + dokumen (LED/LKPS) + tahun. Semua staf yang membuka laporan yang sama
  mengerjakan data yang sama (isian, file upload, hasil ekstraksi, riwayat Word).
- PIN (angka 6-12 digit) dibuat SEKALI per prodi oleh staf pertama yang membuat laporan untuk
  prodi itu, lalu dipakai untuk semua laporan prodi tsb. Daftar laporan (tahun, kelengkapan, terakhir
  diubah) terlihat semua akun; ISI laporan hanya terbuka setelah PIN prodi dimasukkan.
- Akses berlaku per sesi login (akreditasi_prodi_akses terikat token sesi): login ulang = masukkan
  PIN lagi. Salah PIN 5x dalam 15 menit -> dikunci sementara untuk akun+prodi itu (menahan tebakan
  PIN; kolom *_hash tetap bcrypt).
- Lupa PIN: staf mengajukan PIN baru (tersimpan sebagai hash), admin menyetujui/menolak.
  Disetujui -> PIN prodi diganti dan semua akses sesi prodi itu dicabut.
- Hasil ekstraksi AI langsung diterapkan ke data laporan tanpa menimpa isian yang ada: sel
  kosong diisi, baris tabel baru ditambahkan, baris yang sama persis dilewati. Status tiap nilai
  dicatat di akreditasi_upload_ekstraksi.status_terap supaya bisa ditelusuri.

SQL portabel (MySQL lokal, PostgreSQL produksi, SQLite tes).
"""
from __future__ import annotations

import logging
import re
from datetime import datetime, timedelta
from typing import Any

import bcrypt
from sqlalchemy import inspect, text
from sqlalchemy.engine import Engine

from app.domain.source import load_accreditation_module
from app.services import sqlcompat
from app.services.accreditation_auth import token_hash

logger = logging.getLogger(__name__)

DOKUMEN = ("LED", "LKPS")
TAHUN_MIN, TAHUN_MAX = 2000, 2100
PIN_POLA = re.compile(r"[0-9]{6,12}")
MAX_GAGAL = 5
JENDELA_GAGAL = timedelta(minutes=15)
MAX_ALASAN = 500
# Tabel lama yang sekarang milik satu laporan (kolom laporan_id ditambahkan bila belum ada).
TABEL_BERLAPORAN = ("akreditasi_data_manual", "akreditasi_upload_file", "akreditasi_upload_ekstraksi",
                    "akreditasi_riwayat_generate")
STATUS_TERAP = ("ditambahkan", "sudah_ada", "tidak_menimpa", "kolom_lain")


class LaporanError(ValueError):
    """Permintaan tidak valid (400)."""


class AksesDitolak(PermissionError):
    """PIN prodi belum dimasukkan / salah (403)."""


class TidakDitemukan(LookupError):
    """Laporan/prodi/pengajuan tidak ada (404)."""


def _registry():
    return load_accreditation_module("registry_kebutuhan_data.py")


def _hash(password: str) -> str:
    return bcrypt.hashpw(password.encode(), bcrypt.gensalt()).decode()


def _cek_pin_baru(pin: str) -> None:
    if not PIN_POLA.fullmatch(pin or ""):
        raise LaporanError("PIN prodi harus angka 6-12 digit.")


def dokumen_item(item_id: str) -> str | None:
    item = _registry().KEBUTUHAN_DATA.get(item_id)
    return _registry().dokumen_dari_item(item) if item else None


# ---------------------------------------------------------------------- skema
def _table_ddl(engine: Engine) -> list[str]:
    id_clause = {
        "postgresql": "SERIAL PRIMARY KEY",
        "mysql": "INTEGER NOT NULL AUTO_INCREMENT PRIMARY KEY",
        "sqlite": "INTEGER NOT NULL PRIMARY KEY AUTOINCREMENT",
    }.get(engine.dialect.name, "INTEGER NOT NULL PRIMARY KEY")
    return [
        f"""CREATE TABLE IF NOT EXISTS akreditasi_laporan (
            id {id_clause},
            prodi_id VARCHAR(64) NOT NULL,
            dokumen VARCHAR(8) NOT NULL,
            tahun INTEGER NOT NULL,
            nama VARCHAR(150),
            dibuat_oleh VARCHAR(254),
            created_at TIMESTAMP NOT NULL
        )""",
        """CREATE TABLE IF NOT EXISTS akreditasi_prodi_kunci (
            prodi_id VARCHAR(64) NOT NULL PRIMARY KEY,
            password_hash VARCHAR(255) NOT NULL,
            dibuat_oleh VARCHAR(254),
            created_at TIMESTAMP NOT NULL,
            updated_at TIMESTAMP NOT NULL
        )""",
        """CREATE TABLE IF NOT EXISTS akreditasi_prodi_akses (
            token_hash CHAR(64) NOT NULL,
            prodi_id VARCHAR(64) NOT NULL,
            created_at TIMESTAMP NOT NULL,
            PRIMARY KEY (token_hash, prodi_id)
        )""",
        f"""CREATE TABLE IF NOT EXISTS akreditasi_kunci_attempts (
            id {id_clause},
            email VARCHAR(254) NOT NULL,
            prodi_id VARCHAR(64) NOT NULL,
            berhasil BOOLEAN NOT NULL,
            attempted_at TIMESTAMP NOT NULL
        )""",
        f"""CREATE TABLE IF NOT EXISTS akreditasi_reset_kunci (
            id {id_clause},
            prodi_id VARCHAR(64) NOT NULL,
            diajukan_oleh VARCHAR(254) NOT NULL,
            nama_pengaju VARCHAR(100),
            alasan VARCHAR(500),
            password_hash_baru VARCHAR(255) NOT NULL,
            status VARCHAR(16) NOT NULL,
            created_at TIMESTAMP NOT NULL,
            diputus_oleh VARCHAR(254),
            diputus_at TIMESTAMP
        )""",
    ]


def ensure_schema(engine: Engine) -> None:
    """Tabel laporan/kunci + kolom laporan_id & status_terap di tabel lama, lalu migrasi data lama.

    Idempoten; tabel lama yang belum ada (mis. database baru) dilewati.
    """
    with engine.begin() as conn:
        for ddl in _table_ddl(engine):
            conn.execute(text(ddl))
    for ddl in (sqlcompat.index_ddl(engine, "akreditasi_laporan", ["prodi_id", "dokumen", "tahun"],
                                    name="akreditasi_laporan_unik", unique=True),
                sqlcompat.index_ddl(engine, "akreditasi_kunci_attempts", ["email", "prodi_id", "attempted_at"],
                                    name="akreditasi_kunci_attempts_idx")):
        try:
            with engine.begin() as conn:
                conn.execute(text(ddl))
        except Exception as exc:  # noqa: BLE001 -- index sudah ada
            if not sqlcompat.is_duplicate_index_error(exc):
                raise
    ada = set(inspect(engine).get_table_names())
    _samakan_collation(engine, ada)
    for tabel in TABEL_BERLAPORAN:
        if tabel in ada and "laporan_id" not in {c["name"] for c in inspect(engine).get_columns(tabel)}:
            with engine.begin() as conn:
                conn.execute(text(f"ALTER TABLE {tabel} ADD COLUMN laporan_id INTEGER"))
    if "akreditasi_upload_ekstraksi" in ada and "status_terap" not in {
            c["name"] for c in inspect(engine).get_columns("akreditasi_upload_ekstraksi")}:
        with engine.begin() as conn:
            conn.execute(text("ALTER TABLE akreditasi_upload_ekstraksi ADD COLUMN status_terap VARCHAR(16)"))
    if TABEL_BERLAPORAN[0] in ada:
        migrasi_data_lama(engine)
    if "akreditasi_upload_ekstraksi" in ada:
        # Nilai yang dulu sudah dikonfirmasi lewat alur review lama sudah ada di tabel data.
        with engine.begin() as conn:
            conn.execute(text("""
                UPDATE akreditasi_upload_ekstraksi SET status_terap = 'sudah_ada'
                WHERE status_terap IS NULL AND dikonfirmasi_at IS NOT NULL
            """))


TABEL_BARU = ("akreditasi_laporan", "akreditasi_prodi_kunci", "akreditasi_prodi_akses",
              "akreditasi_kunci_attempts", "akreditasi_reset_kunci")


def _samakan_collation(engine: Engine, ada: set[str]) -> None:
    """MySQL: tabel baru mengikuti collation tabel akreditasi lama.

    Tabel baru dibuat dengan collation bawaan koneksi, yang bisa berbeda dari tabel lama
    (lokal: utf8mb4_0900_ai_ci vs utf8mb4_unicode_ci). JOIN kolom teks lintas collation
    ("Illegal mix of collations", 1267) memutus cek akses & daftar reset.
    """
    if engine.dialect.name != "mysql" or "akreditasi_prodi" not in ada:
        return
    with engine.begin() as conn:
        rows = dict(conn.execute(text("""
            SELECT TABLE_NAME, TABLE_COLLATION FROM information_schema.TABLES WHERE TABLE_SCHEMA = DATABASE()
        """)).all())
        acuan = rows.get("akreditasi_prodi")
        if not acuan or not re.fullmatch(r"[A-Za-z0-9_]+", acuan):
            return
        for tabel in TABEL_BARU:
            if rows.get(tabel) and rows[tabel] != acuan:
                conn.execute(text(f"ALTER TABLE {tabel} CONVERT TO CHARACTER SET utf8mb4 COLLATE {acuan}"))


def _laporan_untuk(conn, prodi_id: str, dokumen: str, tahun: int, now: datetime) -> int:
    row = conn.execute(text("""
        SELECT id FROM akreditasi_laporan WHERE prodi_id = :p AND dokumen = :d AND tahun = :t
    """), {"p": prodi_id, "d": dokumen, "t": tahun}).first()
    if row:
        return int(row[0])
    conn.execute(text("""
        INSERT INTO akreditasi_laporan (prodi_id, dokumen, tahun, nama, dibuat_oleh, created_at)
        VALUES (:p, :d, :t, NULL, NULL, :n)
    """), {"p": prodi_id, "d": dokumen, "t": tahun, "n": now})
    return int(conn.execute(text("""
        SELECT id FROM akreditasi_laporan WHERE prodi_id = :p AND dokumen = :d AND tahun = :t
    """), {"p": prodi_id, "d": dokumen, "t": tahun}).scalar_one())


def _tahun(nilai: Any, cadangan: int) -> int:
    try:
        return int(str(nilai)[:4])
    except (TypeError, ValueError):
        return cadangan


def migrasi_data_lama(engine: Engine) -> None:
    """Data sebelum ada laporan (laporan_id NULL) dipindah ke laporan prodi+dokumen, tahun = tahun
    data terakhir diubah; hasil ekstraksi yang belum direview langsung diterapkan ke laporan itu."""
    now = datetime.now()
    ada = set(inspect(engine).get_table_names())
    punya_upload = {"akreditasi_upload_file", "akreditasi_upload_ekstraksi"} <= ada
    with engine.begin() as conn:
        manual = conn.execute(text("""
            SELECT DISTINCT prodi_id, item_id FROM akreditasi_data_manual WHERE laporan_id IS NULL
        """)).all()
        upload_lama = punya_upload and conn.execute(text(
            "SELECT 1 FROM akreditasi_upload_file WHERE laporan_id IS NULL")).first() is not None
        riwayat_lama = "akreditasi_riwayat_generate" in ada and conn.execute(text(
            "SELECT 1 FROM akreditasi_riwayat_generate WHERE laporan_id IS NULL")).first() is not None
        if not manual and not upload_lama and not riwayat_lama:
            return
        terakhir = {r[0]: r[1] for r in conn.execute(text("""
            SELECT prodi_id, MAX(updated_at) FROM akreditasi_data_manual WHERE laporan_id IS NULL GROUP BY prodi_id
        """)).all()}
        for prodi_id, item_id in manual:
            dok = dokumen_item(item_id)
            if not dok:
                continue
            lap = _laporan_untuk(conn, prodi_id, dok, _tahun(terakhir.get(prodi_id), now.year), now)
            conn.execute(text("""
                UPDATE akreditasi_data_manual SET laporan_id = :l
                WHERE prodi_id = :p AND item_id = :i AND laporan_id IS NULL
            """), {"l": lap, "p": prodi_id, "i": item_id})
        uploads = conn.execute(text("""
            SELECT id, prodi_id, uploaded_at FROM akreditasi_upload_file WHERE laporan_id IS NULL
        """)).all() if punya_upload else []
        for upload_id, prodi_id, uploaded_at in uploads:
            items = [r[0] for r in conn.execute(text(
                "SELECT DISTINCT item_id FROM akreditasi_upload_ekstraksi WHERE upload_file_id = :u"), {"u": upload_id})]
            dok = next((d for d in (dokumen_item(i) for i in items) if d), "LED")
            tahun = _tahun(terakhir.get(prodi_id) or uploaded_at, now.year)
            lap = _laporan_untuk(conn, prodi_id, dok, tahun, now)
            conn.execute(text("UPDATE akreditasi_upload_file SET laporan_id = :l WHERE id = :u"), {"l": lap, "u": upload_id})
            conn.execute(text("UPDATE akreditasi_upload_ekstraksi SET laporan_id = :l WHERE upload_file_id = :u"),
                         {"l": lap, "u": upload_id})
        riwayat = conn.execute(text("""
            SELECT id, prodi_id, jenis_dokumen, generated_at FROM akreditasi_riwayat_generate WHERE laporan_id IS NULL
        """)).all() if riwayat_lama else []
        for rid, prodi_id, dok, generated_at in riwayat:
            if dok not in DOKUMEN:
                continue
            lap = _laporan_untuk(conn, prodi_id, dok, _tahun(terakhir.get(prodi_id) or generated_at, now.year), now)
            conn.execute(text("UPDATE akreditasi_riwayat_generate SET laporan_id = :l WHERE id = :r"), {"l": lap, "r": rid})
        # Ekstraksi lama yang belum direview: terapkan ke data laporan (aturan tidak menimpa).
        if not punya_upload:
            return
        pending = conn.execute(text("""
            SELECT e.id, e.laporan_id, e.upload_file_id, e.item_id, e.baris_ke, e.nama_kolom, e.nilai, f.nama_file
            FROM akreditasi_upload_ekstraksi e JOIN akreditasi_upload_file f ON f.id = e.upload_file_id
            WHERE e.dikonfirmasi_at IS NULL AND e.laporan_id IS NOT NULL
            ORDER BY e.upload_file_id, e.id
        """)).mappings().all()
        per_file: dict[tuple[int, int, str], list[dict]] = {}
        for r in pending:
            per_file.setdefault((int(r["laporan_id"]), int(r["upload_file_id"]), r["nama_file"]), []).append(dict(r))
        for (lap, _upload, nama_file), rows in per_file.items():
            prodi_id = conn.execute(text("SELECT prodi_id FROM akreditasi_laporan WHERE id = :l"), {"l": lap}).scalar_one()
            terapkan_ekstraksi(conn, {"id": lap, "prodi_id": prodi_id}, rows, nama_file, now)


# ---------------------------------------------------------------------- terapkan hasil ekstraksi
def _norm(v: Any) -> str:
    return " ".join(str(v or "").split()).casefold()


def terapkan_ekstraksi(conn, laporan: dict[str, Any], rows: list[dict], nama_file: str, now: datetime) -> dict[str, int]:
    """Gabungkan hasil ekstraksi satu file ke data laporan TANPA menimpa isian yang ada.

    `rows`: baris akreditasi_upload_ekstraksi (id, item_id, baris_ke, nama_kolom, nilai) satu file.
    - Kolom di luar kebutuhan item -> "kolom_lain" (tidak dipakai).
    - Item narasi (satu baris): kolom kosong diisi ("ditambahkan"); kolom berisi -> "sama"
      ("sudah_ada") atau berbeda ("tidak_menimpa").
    - Item tabel: tiap baris file dibandingkan dengan baris yang ada. Semua nilainya sudah ada di satu
      baris (abaikan huruf besar/spasi) -> "sudah_ada"; selain itu ditambahkan sebagai baris baru.
    Status tiap nilai ditulis ke status_terap + dikonfirmasi_at.
    """
    registry = _registry()
    per_item: dict[str, list[dict]] = {}
    for r in rows:
        per_item.setdefault(r["item_id"], []).append(r)
    status: dict[int, str] = {}
    sel_baru: list[dict[str, Any]] = []
    for item_id, item_rows in per_item.items():
        item = registry.KEBUTUHAN_DATA.get(item_id)
        if not item:
            status.update({int(r["id"]): "kolom_lain" for r in item_rows})
            continue
        kolom = list(item["kolom_dibutuhkan"])
        ada = conn.execute(text("""
            SELECT baris_ke, kolom, nilai FROM akreditasi_data_manual WHERE laporan_id = :l AND item_id = :i
        """), {"l": laporan["id"], "i": item_id}).all()
        baris_ada: dict[int, dict[str, str]] = {}
        for b, k, v in ada:
            baris_ada.setdefault(int(b), {})[k] = v or ""
        per_baris: dict[int, list[dict]] = {}
        for r in item_rows:
            if r["nama_kolom"] not in kolom or not str(r["nilai"] or "").strip():
                status[int(r["id"])] = "kolom_lain"
                continue
            per_baris.setdefault(int(r["baris_ke"]) if item["tipe"] != "narasi" else 1, []).append(r)
        if item["tipe"] == "narasi":
            isi = baris_ada.get(1, {})
            for r in per_baris.get(1, []):
                k = r["nama_kolom"]
                if not str(isi.get(k, "")).strip():
                    isi[k] = r["nilai"]
                    sel_baru.append({"baris_ke": 1, "kolom": k, "nilai": r["nilai"], "item_id": item_id})
                    status[int(r["id"])] = "ditambahkan"
                else:
                    status[int(r["id"])] = "sudah_ada" if _norm(isi[k]) == _norm(r["nilai"]) else "tidak_menimpa"
            continue
        berikut = max(baris_ada, default=0)
        tanda_ada = [{k: _norm(v) for k, v in b.items() if _norm(v)} for b in baris_ada.values()]
        for _, sel in sorted(per_baris.items()):
            nilai = {s["nama_kolom"]: s["nilai"] for s in sel}
            tanda = {k: _norm(v) for k, v in nilai.items()}
            # Sudah ada = semua nilai baris AI ini sama dengan baris yang ada (baris yang ada boleh lebih lengkap).
            if any(all(b.get(k) == v for k, v in tanda.items()) for b in tanda_ada):
                status.update({int(s["id"]): "sudah_ada" for s in sel})
                continue
            berikut += 1
            tanda_ada.append(tanda)
            for k, v in nilai.items():
                sel_baru.append({"baris_ke": berikut, "kolom": k, "nilai": v, "item_id": item_id})
            status.update({int(s["id"]): "ditambahkan" for s in sel})
    if sel_baru:
        conn.execute(text("""
            INSERT INTO akreditasi_data_manual
              (prodi_id, item_id, baris_ke, kolom, tahun, nilai, link_bukti, diisi_oleh, updated_at, laporan_id)
            VALUES (:prodi_id, :item_id, :baris_ke, :kolom, NULL, :nilai, NULL, :oleh, :t, :l)
        """), [{**c, "prodi_id": laporan["prodi_id"], "oleh": f"AI: {nama_file}"[:255], "t": now, "l": laporan["id"]}
               for c in sel_baru])
    for st in STATUS_TERAP:
        ids = [i for i, s in status.items() if s == st]
        for awal in range(0, len(ids), 500):
            potong = ids[awal:awal + 500]
            params = {f"e{i}": v for i, v in enumerate(potong)}
            conn.execute(text(f"""
                UPDATE akreditasi_upload_ekstraksi SET status_terap = :s, dikonfirmasi_at = :t
                WHERE id IN ({", ".join(":" + k for k in params)})
            """), {**params, "s": st, "t": now})
    return {st: sum(1 for s in status.values() if s == st) for st in STATUS_TERAP}


# ---------------------------------------------------------------------- layanan
class LaporanService:
    def __init__(self, engine: Engine):
        self.engine = engine

    def _prodi(self, conn, prodi_id: str) -> dict[str, Any]:
        row = conn.execute(text("""
            SELECT p.slug, p.nama, p.jenjang, f.nama AS fakultas
            FROM akreditasi_prodi p LEFT JOIN akreditasi_fakultas f ON f.id = p.fakultas_id WHERE p.slug = :s
        """), {"s": prodi_id}).mappings().first()
        if not row:
            raise TidakDitemukan("Program studi tidak ditemukan.")
        return dict(row)

    def terbuka(self, conn, token: str | None, prodi_id: str) -> bool:
        """PIN prodi sudah dimasukkan di sesi login ini (sesi masih berlaku)."""
        if not token:
            return False
        return conn.execute(text("""
            SELECT 1 FROM akreditasi_prodi_akses a JOIN akreditasi_sessions s ON s.token_hash = a.token_hash
            WHERE a.token_hash = :h AND a.prodi_id = :p AND s.expires_at > :now
        """), {"h": token_hash(token), "p": prodi_id, "now": datetime.now()}).first() is not None

    def laporan(self, laporan_id: Any, token: str | None) -> dict[str, Any]:
        """Laporan yang BOLEH dikerjakan sesi ini; AksesDitolak bila PIN prodi belum dimasukkan."""
        try:
            laporan_id = int(laporan_id)
        except (TypeError, ValueError) as exc:
            raise LaporanError("Laporan tidak valid.") from exc
        with self.engine.connect() as conn:
            row = conn.execute(text("""
                SELECT id, prodi_id, dokumen, tahun, nama FROM akreditasi_laporan WHERE id = :id
            """), {"id": laporan_id}).mappings().first()
            if not row:
                raise TidakDitemukan("Laporan tidak ditemukan.")
            if not self.terbuka(conn, token, row["prodi_id"]):
                raise AksesDitolak("Masukkan PIN prodi untuk membuka laporan ini.")
        return dict(row)

    def daftar(self, prodi_id: str, dokumen: str, token: str | None, email: str) -> dict[str, Any]:
        if dokumen not in DOKUMEN:
            raise LaporanError("Dokumen harus LED atau LKPS.")
        registry = _registry()
        grouped = registry.led_items_by_kriteria() if dokumen == "LED" else registry.lkps_items_by_bagian()
        item_ids = [i["id"] for items in grouped.values() for i in items]
        from app.services import accreditation_sumber as sumber
        with self.engine.connect() as conn:
            prodi = self._prodi(conn, prodi_id)
            rows = conn.execute(text("""
                SELECT id, tahun, nama, dibuat_oleh, created_at FROM akreditasi_laporan
                WHERE prodi_id = :p AND dokumen = :d ORDER BY tahun DESC, id DESC
            """), {"p": prodi_id, "d": dokumen}).mappings().all()
            isi = conn.execute(text("""
                SELECT laporan_id, item_id, diisi_oleh, updated_at FROM akreditasi_data_manual
                WHERE prodi_id = :p AND laporan_id IS NOT NULL
            """), {"p": prodi_id}).mappings().all()
            live_ids = set(sumber.data_live(conn, prodi_id)["items"])
            terkunci = conn.execute(text("SELECT 1 FROM akreditasi_prodi_kunci WHERE prodi_id = :p"),
                                    {"p": prodi_id}).first() is not None
            buka = self.terbuka(conn, token, prodi_id)
            reset = conn.execute(text("""
                SELECT 1 FROM akreditasi_reset_kunci WHERE prodi_id = :p AND diajukan_oleh = :e AND status = 'menunggu'
            """), {"p": prodi_id, "e": email}).first() is not None
        hasil = []
        for r in rows:
            milik = [x for x in isi if int(x["laporan_id"]) == int(r["id"])]
            ringkas = sumber.ringkasan(item_ids, {x["item_id"] for x in milik}, live_ids)
            akhir = max(milik, key=lambda x: str(x["updated_at"] or ""), default=None)
            hasil.append({
                "id": int(r["id"]), "tahun": int(r["tahun"]), "nama": r["nama"] or f"{dokumen} {r['tahun']}",
                "dibuat_oleh": r["dibuat_oleh"], "dibuat": _iso(r["created_at"]),
                "lengkap": ringkas["lengkap"], "total": ringkas["total"], "persen": ringkas["persen"],
                "terakhir_diubah": _iso(akhir["updated_at"]) if akhir else None,
                "terakhir_oleh": akhir["diisi_oleh"] if akhir else None,
            })
        return {"prodi": prodi, "dokumen": dokumen, "terkunci": terkunci, "terbuka": buka,
                "reset_menunggu": reset, "laporan": hasil}

    def _catat(self, conn, email: str, prodi_id: str, berhasil: bool) -> None:
        conn.execute(text("""
            INSERT INTO akreditasi_kunci_attempts (email, prodi_id, berhasil, attempted_at) VALUES (:e, :p, :b, :t)
        """), {"e": email, "p": prodi_id, "b": berhasil, "t": datetime.now()})

    def _terkunci_sementara(self, conn, email: str, prodi_id: str) -> bool:
        rows = conn.execute(text("""
            SELECT berhasil FROM akreditasi_kunci_attempts
            WHERE email = :e AND prodi_id = :p AND attempted_at >= :since
            ORDER BY attempted_at DESC, id DESC LIMIT :n
        """), {"e": email, "p": prodi_id, "since": datetime.now() - JENDELA_GAGAL, "n": MAX_GAGAL}).all()
        return len(rows) >= MAX_GAGAL and not any(bool(r[0]) for r in rows)

    def _buka_sesi(self, conn, token: str, prodi_id: str) -> None:
        h = token_hash(token)
        conn.execute(text("DELETE FROM akreditasi_prodi_akses WHERE token_hash = :h AND prodi_id = :p"), {"h": h, "p": prodi_id})
        conn.execute(text("""
            INSERT INTO akreditasi_prodi_akses (token_hash, prodi_id, created_at) VALUES (:h, :p, :t)
        """), {"h": h, "p": prodi_id, "t": datetime.now()})

    def buat_kunci(self, prodi_id: str, password: str, token: str, email: str) -> dict[str, Any]:
        """PIN pertama prodi (hanya bila belum ada); sesi ini langsung terbuka."""
        _cek_pin_baru(password)
        now = datetime.now()
        with self.engine.begin() as conn:
            self._prodi(conn, prodi_id)
            if conn.execute(text("SELECT 1 FROM akreditasi_prodi_kunci WHERE prodi_id = :p"), {"p": prodi_id}).first():
                raise LaporanError("Prodi ini sudah punya PIN. Masukkan PIN tersebut, atau ajukan reset.")
            conn.execute(text("""
                INSERT INTO akreditasi_prodi_kunci (prodi_id, password_hash, dibuat_oleh, created_at, updated_at)
                VALUES (:p, :h, :e, :t, :t)
            """), {"p": prodi_id, "h": _hash(password), "e": email, "t": now})
            self._buka_sesi(conn, token, prodi_id)
        return {"message": "PIN prodi dibuat. Bagikan ke staf prodi yang ikut menyusun laporan."}

    def buka(self, prodi_id: str, password: str, token: str, email: str) -> dict[str, Any]:
        with self.engine.begin() as conn:
            self._prodi(conn, prodi_id)
            row = conn.execute(text("SELECT password_hash FROM akreditasi_prodi_kunci WHERE prodi_id = :p"),
                               {"p": prodi_id}).first()
            if not row:
                raise LaporanError("Prodi ini belum punya PIN. Buat PIN dulu.")
            if self._terkunci_sementara(conn, email, prodi_id):
                raise AksesDitolak(f"Terlalu banyak percobaan salah. Coba lagi dalam {int(JENDELA_GAGAL.total_seconds() // 60)} menit.")
            benar = bool(PIN_POLA.fullmatch(password or "")) and bcrypt.checkpw(password.encode(), row[0].encode())
            self._catat(conn, email, prodi_id, benar)
            if benar:
                self._buka_sesi(conn, token, prodi_id)
        if not benar:
            raise AksesDitolak("PIN prodi salah.")
        return {"message": "Laporan prodi terbuka untuk sesi ini."}

    def buat_laporan(self, prodi_id: str, dokumen: str, tahun: Any, nama: str, token: str, email: str) -> dict[str, Any]:
        if dokumen not in DOKUMEN:
            raise LaporanError("Dokumen harus LED atau LKPS.")
        try:
            tahun = int(tahun)
        except (TypeError, ValueError) as exc:
            raise LaporanError("Tahun laporan tidak valid.") from exc
        if not TAHUN_MIN <= tahun <= TAHUN_MAX:
            raise LaporanError(f"Tahun laporan harus {TAHUN_MIN}-{TAHUN_MAX}.")
        nama = (nama or "").strip()[:150] or None
        now = datetime.now()
        with self.engine.begin() as conn:
            self._prodi(conn, prodi_id)
            if not self.terbuka(conn, token, prodi_id):
                raise AksesDitolak("Masukkan PIN prodi dulu sebelum membuat laporan.")
            if conn.execute(text("""
                SELECT 1 FROM akreditasi_laporan WHERE prodi_id = :p AND dokumen = :d AND tahun = :t
            """), {"p": prodi_id, "d": dokumen, "t": tahun}).first():
                raise LaporanError(f"Laporan {dokumen} {tahun} untuk prodi ini sudah ada. Lanjutkan dari riwayat.")
            conn.execute(text("""
                INSERT INTO akreditasi_laporan (prodi_id, dokumen, tahun, nama, dibuat_oleh, created_at)
                VALUES (:p, :d, :t, :n, :e, :c)
            """), {"p": prodi_id, "d": dokumen, "t": tahun, "n": nama, "e": email, "c": now})
            lap_id = conn.execute(text("""
                SELECT id FROM akreditasi_laporan WHERE prodi_id = :p AND dokumen = :d AND tahun = :t
            """), {"p": prodi_id, "d": dokumen, "t": tahun}).scalar_one()
        return {"id": int(lap_id), "tahun": tahun, "nama": nama or f"{dokumen} {tahun}"}

    # ------------------------------------------------------------------ reset PIN
    def ajukan_reset(self, prodi_id: str, password_baru: str, alasan: str, user: dict[str, Any]) -> dict[str, Any]:
        _cek_pin_baru(password_baru)
        alasan = (alasan or "").strip()[:MAX_ALASAN]
        with self.engine.begin() as conn:
            self._prodi(conn, prodi_id)
            if not conn.execute(text("SELECT 1 FROM akreditasi_prodi_kunci WHERE prodi_id = :p"), {"p": prodi_id}).first():
                raise LaporanError("Prodi ini belum punya PIN; buat PIN langsung, tanpa reset.")
            # Satu pengajuan menunggu per akun per prodi: pengajuan baru menggantikan yang lama.
            conn.execute(text("""
                DELETE FROM akreditasi_reset_kunci WHERE prodi_id = :p AND diajukan_oleh = :e AND status = 'menunggu'
            """), {"p": prodi_id, "e": user["email"]})
            conn.execute(text("""
                INSERT INTO akreditasi_reset_kunci
                  (prodi_id, diajukan_oleh, nama_pengaju, alasan, password_hash_baru, status, created_at)
                VALUES (:p, :e, :n, :a, :h, 'menunggu', :t)
            """), {"p": prodi_id, "e": user["email"], "n": user.get("nama"), "a": alasan or None,
                   "h": _hash(password_baru), "t": datetime.now()})
        return {"message": "Pengajuan reset terkirim. PIN baru berlaku setelah disetujui admin."}

    def daftar_reset(self, status: str | None = None) -> list[dict[str, Any]]:
        with self.engine.connect() as conn:
            rows = conn.execute(text("""
                SELECT r.id, r.prodi_id, p.nama AS nama_prodi, p.jenjang, f.nama AS fakultas, r.diajukan_oleh, r.nama_pengaju,
                       r.alasan, r.status, r.created_at, r.diputus_oleh, r.diputus_at
                FROM akreditasi_reset_kunci r
                LEFT JOIN akreditasi_prodi p ON p.slug = r.prodi_id
                LEFT JOIN akreditasi_fakultas f ON f.id = p.fakultas_id
                ORDER BY CASE WHEN r.status = 'menunggu' THEN 0 ELSE 1 END, r.created_at DESC, r.id DESC
            """)).mappings().all()
        return [{**{k: v for k, v in dict(r).items() if k not in ("created_at", "diputus_at")},
                 "created_at": _iso(r["created_at"]), "diputus_at": _iso(r["diputus_at"])}
                for r in rows if status is None or r["status"] == status][:200]

    def putuskan_reset(self, reset_id: int, setujui: bool, admin: dict[str, Any]) -> dict[str, Any]:
        now = datetime.now()
        with self.engine.begin() as conn:
            row = conn.execute(text("""
                SELECT prodi_id, password_hash_baru, status FROM akreditasi_reset_kunci WHERE id = :id
            """), {"id": reset_id}).mappings().first()
            if not row:
                raise TidakDitemukan("Pengajuan tidak ditemukan.")
            if row["status"] != "menunggu":
                raise LaporanError("Pengajuan ini sudah diputuskan.")
            conn.execute(text("""
                UPDATE akreditasi_reset_kunci SET status = :s, diputus_oleh = :a, diputus_at = :t WHERE id = :id
            """), {"s": "disetujui" if setujui else "ditolak", "a": admin["email"], "t": now, "id": reset_id})
            if setujui:
                conn.execute(text("""
                    UPDATE akreditasi_prodi_kunci SET password_hash = :h, updated_at = :t WHERE prodi_id = :p
                """), {"h": row["password_hash_baru"], "t": now, "p": row["prodi_id"]})
                # PIN lama tidak berlaku lagi: semua sesi yang terbuka dengan PIN lama ditutup,
                # dan pengajuan lain yang masih menunggu untuk prodi ini ikut gugur.
                conn.execute(text("DELETE FROM akreditasi_prodi_akses WHERE prodi_id = :p"), {"p": row["prodi_id"]})
                conn.execute(text("""
                    UPDATE akreditasi_reset_kunci SET status = 'gugur', diputus_oleh = :a, diputus_at = :t
                    WHERE prodi_id = :p AND status = 'menunggu'
                """), {"a": admin["email"], "t": now, "p": row["prodi_id"]})
        return {"message": "Pengajuan disetujui: PIN prodi diganti." if setujui else "Pengajuan ditolak."}


def _iso(nilai: Any) -> str | None:
    if nilai is None:
        return None
    return nilai.isoformat() if hasattr(nilai, "isoformat") else str(nilai)
