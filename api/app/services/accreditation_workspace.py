"""Ruang kerja akreditasi: isi data satu LAPORAN (prodi + LED/LKPS + tahun), ekstraksi AI, Word.

Setiap method menerima laporan yang SUDAH lolos cek akses (password prodi dibuka di sesi ini,
lihat services/accreditation_laporan.py); semua baca/tulis dibatasi `laporan_id` sehingga
staf satu prodi mengerjakan data yang sama dan laporan tahun berbeda tidak saling menimpa.

- Data resmi = akreditasi_data_manual (skema long/EAV: satu baris = satu sel). Simpan satu
  item = hapus semua sel item itu di laporan tsb lalu tulis ulang.
- Item berstatus "belum_tersedia" tidak bisa diisi.
- Hasil ekstraksi AI langsung diterapkan ke data laporan tanpa menimpa isian yang ada
  (accreditation_laporan.terapkan_ekstraksi); status tiap nilai tercatat sebagai riwayat.
- Status tiap item = akreditasi/data_source_map.json (services/accreditation_sumber.py).
  Item "tersedia" membawa data live pipeline Fase 2; isian tim tetap bisa menggantikannya.
- Generate Word memakai builder akreditasi/scripts/generate_template.py (isian tim + data live +
  status peta), dicatat di akreditasi_riwayat_generate dan bisa diunduh semua staf laporan itu.

Semua SQL standar (tanpa backtick/dialek) supaya jalan di MySQL (pratinjau lokal) maupun
PostgreSQL (produksi).
"""
from __future__ import annotations

import logging
import os
import re
import threading
import unicodedata
from datetime import datetime
from pathlib import Path
from typing import Any, Callable

import pandas as pd
from sqlalchemy import text
from sqlalchemy.engine import Engine

from app.domain.source import load_accreditation_module
from app.services import accreditation_sumber as sumber
from app.services.accreditation_laporan import terapkan_ekstraksi

logger = logging.getLogger(__name__)

DOKUMEN = ("LED", "LKPS")
JENJANG = ("Sarjana", "Magister", "Doktor", "Profesi", "Spesialis")
MAX_ROWS_PER_ITEM = 500
MAX_VALUE_CHARS = 20_000
MAX_RIWAYAT = 20

# Status ekstraksi per file upload yang sedang berjalan DI PROSES INI. Satu proses API
# (uvicorn tanpa --workers) -- cukup untuk pratinjau lokal & deploy saat ini.
_JOBS: dict[int, dict[str, Any]] = {}
_JOBS_LOCK = threading.Lock()

Extractor = Callable[[str, str, str, Callable[[int, int], None]], tuple[list[dict], dict]]


class WorkspaceError(ValueError):
    """Permintaan tidak valid (400)."""


class NotFound(LookupError):
    """Prodi/item/riwayat tidak ditemukan (404)."""


def _registry():
    return load_accreditation_module("registry_kebutuhan_data.py")


def _default_extractor(path: str, tipe: str, dokumen: str, progress: Callable[[int, int], None]):
    module = load_accreditation_module("ekstraksi_akreditasi.py")
    return module.ekstrak_dokumen(path, tipe, dokumen, progress_callback=progress)


def extraction_available() -> bool:
    return bool(os.environ.get("OPENAI_API_KEY"))


def _iso(value: Any) -> str | None:
    if value is None or value == "":
        return None
    if isinstance(value, datetime):
        return value.isoformat(timespec="seconds")
    return str(value)


def slugify(nama: str) -> str:
    """"Magister Kecerdasan Artifisial" -> "magister-kecerdasan-artifisial"."""
    ascii_only = unicodedata.normalize("NFKD", nama).encode("ascii", "ignore").decode("ascii")
    return re.sub(r"[^a-z0-9]+", "-", ascii_only.lower()).strip("-")[:56] or "prodi"


def _nama_laporan(laporan: dict[str, Any]) -> str:
    return laporan.get("nama") or f"{laporan['dokumen']} {laporan['tahun']}"


class AccreditationWorkspaceService:
    def __init__(self, engine: Engine, upload_root: Path | None = None, generated_root: Path | None = None,
                 extractor: Extractor | None = None):
        self.engine = engine
        self.upload_root = upload_root
        self.generated_root = generated_root
        self.extractor = extractor or _default_extractor

    # ------------------------------------------------------------------ baca
    def _program(self, conn, prodi_id: str) -> dict[str, Any]:
        row = conn.execute(text("""
            SELECT p.slug, p.nama, p.jenjang, f.nama AS fakultas
            FROM akreditasi_prodi p LEFT JOIN akreditasi_fakultas f ON f.id = p.fakultas_id
            WHERE p.slug = :slug
        """), {"slug": prodi_id}).mappings().first()
        if not row:
            raise NotFound("Program studi tidak ditemukan.")
        return dict(row)

    def workspace(self, laporan: dict[str, Any]) -> dict[str, Any]:
        registry = _registry()
        lap_id, prodi_id, dokumen = int(laporan["id"]), laporan["prodi_id"], laporan["dokumen"]
        with self.engine.connect() as conn:
            program = self._program(conn, prodi_id)
            manual = conn.execute(text("""
                SELECT item_id, baris_ke, kolom, nilai, diisi_oleh, updated_at
                FROM akreditasi_data_manual WHERE laporan_id = :l
            """), {"l": lap_id}).mappings().all()
            ekstraksi = conn.execute(text("""
                SELECT e.id, e.item_id, e.baris_ke, e.nama_kolom, e.nilai, e.kutipan, e.status_terap, f.nama_file
                FROM akreditasi_upload_ekstraksi e
                JOIN akreditasi_upload_file f ON f.id = e.upload_file_id
                WHERE e.laporan_id = :l
                ORDER BY f.uploaded_at DESC, e.item_id, e.baris_ke, e.nama_kolom, e.id
            """), {"l": lap_id}).mappings().all()
            uploads = conn.execute(text("""
                SELECT id, nama_file, tipe_file, ukuran_bytes, status, diupload_oleh, uploaded_at, diekstrak_at
                FROM akreditasi_upload_file WHERE laporan_id = :l ORDER BY uploaded_at DESC, id DESC
            """), {"l": lap_id}).mappings().all()
            riwayat = conn.execute(text("""
                SELECT id, user_email, generated_at FROM akreditasi_riwayat_generate
                WHERE laporan_id = :l ORDER BY generated_at DESC, id DESC
            """), {"l": lap_id}).mappings().all()
            # Cuplikan tabel LKPS di tab LED: terisi menurut laporan LKPS prodi yang sama di tahun yang sama.
            lkps_terisi = {r[0] for r in conn.execute(text("""
                SELECT DISTINCT d.item_id FROM akreditasi_data_manual d
                JOIN akreditasi_laporan l ON l.id = d.laporan_id
                WHERE l.prodi_id = :p AND l.dokumen = 'LKPS' AND l.tahun = :t
            """), {"p": prodi_id, "t": laporan["tahun"]})} if dokumen == "LED" else set()
            live = sumber.data_live(conn, prodi_id)

        manual_by_item: dict[str, list[dict]] = {}
        for row in manual:
            manual_by_item.setdefault(row["item_id"], []).append(dict(row))
        filled_ids = set(manual_by_item)

        grouped = registry.led_items_by_kriteria() if dokumen == "LED" else registry.lkps_items_by_bagian()
        labels = registry.LABEL_KRITERIA if dokumen == "LED" else registry.LABEL_BAGIAN_LKPS
        groups = []
        for key, items in grouped.items():
            group = {
                "key": key,
                "label": labels.get(key, key),
                "items": [self._item_payload(registry, item, manual_by_item.get(item["id"], []), live) for item in items],
                "cuplikan": [],
            }
            if dokumen == "LED" and key not in ("Umum", "D"):
                group["cuplikan"] = [
                    {"id": c["id"], "tabel_lkps": c["tabel_lkps"], "nama": c["nama"],
                     "status": c["status_ketersediaan"],
                     "terisi": c["id"] in lkps_terisi or c["id"] in live["items"]}
                    for c in registry.lkps_cuplikan_untuk_kriteria(key)
                ]
            groups.append(group)

        item_ids = [item["id"] for items in grouped.values() for item in items]
        grup_item = {item["id"]: key for key, items in grouped.items() for item in items}
        nama_item = {item["id"]: item["nama"] for items in grouped.values() for item in items}
        return {
            "laporan": {"id": lap_id, "tahun": int(laporan["tahun"]), "nama": _nama_laporan(laporan)},
            "prodi": program,
            "dokumen": dokumen,
            "ringkasan": sumber.ringkasan(item_ids, filled_ids, set(live["items"])),
            "groups": groups,
            "uploads": [self._upload_payload(dict(row)) for row in uploads],
            "ekstraksi": {
                "tersedia": extraction_available(),
                "riwayat": [
                    {"id": int(r["id"]), "item_id": r["item_id"], "item_nama": nama_item[r["item_id"]],
                     "grup": grup_item[r["item_id"]], "baris_ke": int(r["baris_ke"]), "kolom": r["nama_kolom"],
                     "nilai": r["nilai"], "kutipan": r["kutipan"], "nama_file": r["nama_file"],
                     "status": r["status_terap"] or "sudah_ada"}
                    for r in ekstraksi if r["item_id"] in grup_item
                ],
            },
            "riwayat_word": [{"id": int(r["id"]), "oleh": r["user_email"], "waktu": _iso(r["generated_at"])}
                             for r in riwayat[:MAX_RIWAYAT]],
        }

    @staticmethod
    def _upload_payload(row: dict[str, Any]) -> dict[str, Any]:
        with _JOBS_LOCK:
            job = dict(_JOBS.get(int(row["id"]), {}))
        status = row["status"]
        if status == "sedang_diekstrak" and not job.get("berjalan"):
            status = "terhenti"  # proses API mati di tengah ekstraksi; boleh diulang
        return {
            "id": int(row["id"]), "nama_file": row["nama_file"], "tipe_file": row["tipe_file"],
            "ukuran_bytes": int(row["ukuran_bytes"] or 0), "status": status,
            "diupload_oleh": row.get("diupload_oleh"),
            "uploaded_at": _iso(row["uploaded_at"]), "diekstrak_at": _iso(row["diekstrak_at"]),
            "progres": {"batch": job.get("batch", 0), "total": job.get("total", 0)} if job.get("berjalan") else None,
            "ringkasan": job.get("ringkasan"),
        }

    @staticmethod
    def _item_payload(registry, item: dict, manual: list[dict], live: dict[str, Any]) -> dict[str, Any]:
        kolom = list(item["kolom_dibutuhkan"])
        status = item["status_ketersediaan"]
        terisi = bool(manual)
        data_live = live["items"].get(item["id"])
        if status == "belum_tersedia":
            state = "belum_tersedia"
        elif terisi:
            state = "terisi"
        elif data_live:
            state = "live"
        else:
            state = "kosong"

        if item["tipe"] == "narasi":
            existing = {r["kolom"]: r["nilai"] or "" for r in manual if int(r["baris_ke"]) == 1}
            rows = [{k: existing.get(k, "") for k in kolom}]
        else:
            by_row: dict[int, dict[str, str]] = {}
            for r in manual:
                by_row.setdefault(int(r["baris_ke"]), {})[r["kolom"]] = r["nilai"] or ""
            rows = [{k: by_row[b].get(k, "") for k in kolom} for b in sorted(by_row)] or [{k: "" for k in kolom}]

        terakhir = max(manual, key=lambda r: str(r["updated_at"] or ""), default=None)
        return {
            "id": item["id"], "nama": item["nama"], "deskripsi": item["deskripsi_singkat"],
            "sumber_data": item["sumber_data"], "status": status,
            "status_label": registry.STATUS_LABEL.get(status, status),
            "tipe": item["tipe"], "kolom": kolom, "tabel_lkps": item["tabel_lkps"],
            "narasi": bool(registry.is_narasi_penilaian(item)),
            "terisi": terisi, "state": state, "editable": status != "belum_tersedia",
            "rows": rows,
            "diisi_oleh": terakhir["diisi_oleh"] if terakhir else None,
            "updated_at": _iso(terakhir["updated_at"]) if terakhir else None,
            **sumber.info_item(item["id"]),
            "live": ({"kolom": kolom + list(dict.fromkeys(k for r in data_live["rows"] for k in r if k not in kolom)),
                      "rows": data_live["rows"], "sumber": data_live["sumber"],
                      "fetched_at": _iso(data_live["fetched_at"])} if data_live else None),
            "pendukung": sumber.pendukung(item["id"], live),
        }

    # ------------------------------------------------------------------ tulis
    def save_item(self, laporan: dict[str, Any], item_id: str, rows: Any, user_email: str) -> dict[str, Any]:
        registry = _registry()
        item = registry.KEBUTUHAN_DATA.get(item_id)
        if not item:
            raise NotFound("Item kebutuhan data tidak dikenal.")
        if registry.dokumen_dari_item(item) != laporan["dokumen"]:
            raise WorkspaceError(f"Item ini bukan bagian dokumen {laporan['dokumen']}.")
        if item["status_ketersediaan"] == "belum_tersedia":
            raise WorkspaceError("Item ini belum bisa diisi (status belum tersedia).")
        if not isinstance(rows, list) or not all(isinstance(r, dict) for r in rows):
            raise WorkspaceError("Format baris tidak valid.")
        if len(rows) > MAX_ROWS_PER_ITEM:
            raise WorkspaceError(f"Maksimal {MAX_ROWS_PER_ITEM} baris per item.")
        if item["tipe"] == "narasi":
            rows = rows[:1]

        kolom = list(item["kolom_dibutuhkan"])
        now = datetime.now()
        cells: list[dict[str, Any]] = []
        baris_ke = 0
        for row in rows:
            values = {k: ("" if row.get(k) is None else str(row.get(k))) for k in kolom}
            if not any(v.strip() for v in values.values()):
                continue  # baris kosong tidak disimpan & tidak memakan nomor baris
            baris_ke += 1
            for k, v in values.items():
                if not v.strip():
                    continue
                if len(v) > MAX_VALUE_CHARS:
                    raise WorkspaceError(f"Isian kolom \"{k}\" terlalu panjang (maks. {MAX_VALUE_CHARS} karakter).")
                cells.append({"prodi_id": laporan["prodi_id"], "laporan_id": int(laporan["id"]), "item_id": item_id,
                              "baris_ke": baris_ke, "kolom": k, "nilai": v, "diisi_oleh": user_email, "updated_at": now})

        with self.engine.begin() as conn:
            conn.execute(text("DELETE FROM akreditasi_data_manual WHERE laporan_id = :l AND item_id = :i"),
                         {"l": int(laporan["id"]), "i": item_id})
            if cells:
                conn.execute(text("""
                    INSERT INTO akreditasi_data_manual
                      (prodi_id, laporan_id, item_id, baris_ke, kolom, tahun, nilai, link_bukti, diisi_oleh, updated_at)
                    VALUES (:prodi_id, :laporan_id, :item_id, :baris_ke, :kolom, NULL, :nilai, NULL, :diisi_oleh, :updated_at)
                """), cells)
        return {"message": "Tersimpan.", "baris": baris_ke, "sel": len(cells)}

    def add_program(self, fakultas_id: Any, nama: str, jenjang: str) -> dict[str, Any]:
        nama = (nama or "").strip()
        if not nama or len(nama) > 150:
            raise WorkspaceError("Nama program studi wajib diisi (maks. 150 karakter).")
        if jenjang not in JENJANG:
            raise WorkspaceError("Jenjang tidak dikenal.")
        try:
            fakultas_id = int(fakultas_id)
        except (TypeError, ValueError) as exc:
            raise WorkspaceError("Fakultas tidak valid.") from exc
        base = slugify(nama)
        with self.engine.begin() as conn:
            if not conn.execute(text("SELECT 1 FROM akreditasi_fakultas WHERE id = :id"), {"id": fakultas_id}).first():
                raise NotFound("Fakultas tidak ditemukan.")
            ada = conn.execute(text("""
                SELECT slug FROM akreditasi_prodi WHERE fakultas_id = :f AND LOWER(nama) = :n
            """), {"f": fakultas_id, "n": nama.lower()}).first()
            if ada:
                raise WorkspaceError("Program studi dengan nama itu sudah ada di fakultas ini.")
            slug, i = base, 2
            while conn.execute(text("SELECT 1 FROM akreditasi_prodi WHERE slug = :s"), {"s": slug}).first():
                slug, i = f"{base}-{i}", i + 1
            conn.execute(text("""
                INSERT INTO akreditasi_prodi (fakultas_id, nama, jenjang, slug) VALUES (:f, :n, :j, :s)
            """), {"f": fakultas_id, "n": nama, "j": jenjang, "s": slug})
        return {"slug": slug, "nama": nama, "jenjang": jenjang, "fakultas_id": fakultas_id}

    # ------------------------------------------------------------------ Word
    def generate(self, laporan: dict[str, Any], user_email: str) -> tuple[bytes, str]:
        if self.generated_root is None:
            raise RuntimeError("Folder dokumen hasil generate belum dikonfigurasi.")
        lap_id, prodi_id, dokumen = int(laporan["id"]), laporan["prodi_id"], laporan["dokumen"]
        with self.engine.connect() as conn:
            program = self._program(conn, prodi_id)
            df = pd.read_sql(text("""
                SELECT item_id, baris_ke, kolom, tahun, nilai, link_bukti
                FROM akreditasi_data_manual WHERE laporan_id = :l
            """), conn, params={"l": lap_id})
            live = sumber.data_live(conn, prodi_id)
        generator = load_accreditation_module("generate_template.py")
        konteks = {
            "prodi": f"{program.get('jenjang') or ''} {program['nama']}".strip() + f" — {_nama_laporan(laporan)}",
            "fakultas": program.get("fakultas"),
            "peta": sumber.peta(),
            "live": live,
        }
        build = generator.build_led_docx if dokumen == "LED" else generator.build_lkps_docx
        content = build(df, konteks=konteks)

        now = datetime.now()
        folder = (self.generated_root / re.sub(r"[^A-Za-z0-9_-]", "_", prodi_id)).resolve()
        folder.mkdir(parents=True, exist_ok=True)
        path = folder / f"{now:%Y%m%d_%H%M%S_%f}_{dokumen}_{laporan['tahun']}.docx"
        path.write_bytes(content)
        try:
            with self.engine.begin() as conn:
                conn.execute(text("""
                    INSERT INTO akreditasi_riwayat_generate
                      (user_email, prodi_id, laporan_id, jenis_dokumen, file_path, generated_at)
                    VALUES (:e, :p, :l, :j, :f, :t)
                """), {"e": user_email, "p": prodi_id, "l": lap_id, "j": dokumen, "f": str(path), "t": now})
        except Exception:
            path.unlink(missing_ok=True)  # jangan tinggalkan file yatim
            raise
        return content, f"Laporan_Akreditasi_{dokumen}_{laporan['tahun']}_{prodi_id}_{now:%Y%m%d}.docx"

    def _berkas(self, row: dict[str, Any] | None) -> tuple[bytes, str]:
        if not row or self.generated_root is None:
            raise NotFound("Riwayat tidak ditemukan.")
        path = Path(row["file_path"]).resolve()
        if not path.is_relative_to(self.generated_root.resolve()) or not path.is_file():
            raise NotFound("Berkas laporan ini sudah tidak tersedia di server.")
        stamp = str(row["generated_at"] or "")[:10].replace("-", "")
        tahun = f"_{row['tahun']}" if row.get("tahun") else ""
        return path.read_bytes(), f"Laporan_Akreditasi_{row['jenis_dokumen']}{tahun}_{row['prodi_id']}_{stamp}.docx"

    def history_file(self, riwayat_id: int, user_email: str) -> tuple[bytes, str]:
        """File riwayat milik user sendiri (halaman Profil). Path dari DB tetap dicek berada di folder generate."""
        with self.engine.connect() as conn:
            row = conn.execute(text("""
                SELECT r.prodi_id, r.jenis_dokumen, r.file_path, r.generated_at, l.tahun
                FROM akreditasi_riwayat_generate r LEFT JOIN akreditasi_laporan l ON l.id = r.laporan_id
                WHERE r.id = :id AND r.user_email = :e
            """), {"id": riwayat_id, "e": user_email}).mappings().first()
        return self._berkas(dict(row) if row else None)

    def laporan_file(self, laporan: dict[str, Any], riwayat_id: int) -> tuple[bytes, str]:
        """File riwayat Word suatu laporan, untuk semua staf yang sudah membuka laporan itu."""
        with self.engine.connect() as conn:
            row = conn.execute(text("""
                SELECT r.prodi_id, r.jenis_dokumen, r.file_path, r.generated_at, l.tahun
                FROM akreditasi_riwayat_generate r JOIN akreditasi_laporan l ON l.id = r.laporan_id
                WHERE r.id = :id AND r.laporan_id = :l
            """), {"id": riwayat_id, "l": int(laporan["id"])}).mappings().first()
        return self._berkas(dict(row) if row else None)

    # ------------------------------------------------------------------ hapus laporan
    def hapus_laporan(self, laporan: dict[str, Any]) -> dict[str, Any]:
        """Hapus satu laporan beserta isian, file upload, riwayat ekstraksi, dan riwayat Word-nya.

        Berkas di disk dihapus SETELAH transaksi DB berhasil, dan hanya yang berada di folder
        upload/generate (path berasal dari DB, tetap dicek).
        """
        lap_id = int(laporan["id"])
        with self.engine.begin() as conn:
            berkas = [r[0] for r in conn.execute(text(
                "SELECT path_lokal FROM akreditasi_upload_file WHERE laporan_id = :l"), {"l": lap_id})]
            berkas += [r[0] for r in conn.execute(text(
                "SELECT file_path FROM akreditasi_riwayat_generate WHERE laporan_id = :l"), {"l": lap_id})]
            n_isian = conn.execute(text("SELECT COUNT(*) FROM akreditasi_data_manual WHERE laporan_id = :l"),
                                   {"l": lap_id}).scalar() or 0
            for tabel in ("akreditasi_upload_ekstraksi", "akreditasi_upload_file", "akreditasi_data_manual",
                          "akreditasi_riwayat_generate"):
                conn.execute(text(f"DELETE FROM {tabel} WHERE laporan_id = :l"), {"l": lap_id})
            conn.execute(text("DELETE FROM akreditasi_laporan WHERE id = :l"), {"l": lap_id})
        akar = [r.resolve() for r in (self.upload_root, self.generated_root) if r is not None]
        for nama in berkas:
            path = Path(nama).resolve()
            if any(path.is_relative_to(a) for a in akar):
                path.unlink(missing_ok=True)
        return {"message": f"{_nama_laporan(laporan)} dihapus ({n_isian} sel isian, {len(berkas)} berkas)."}

    # ------------------------------------------------------------------ ekstraksi AI
    def start_extraction(self, laporan: dict[str, Any], background: bool = True) -> dict[str, Any]:
        if not extraction_available():
            raise WorkspaceError("Ekstraksi AI belum dikonfigurasi (OPENAI_API_KEY kosong di .env).")
        with self.engine.connect() as conn:
            candidates = conn.execute(text("""
                SELECT id, status FROM akreditasi_upload_file
                WHERE laporan_id = :l AND status IN ('belum_diekstrak', 'gagal_ekstrak', 'sedang_diekstrak')
                ORDER BY uploaded_at, id
            """), {"l": int(laporan["id"])}).mappings().all()
        claimed: list[int] = []
        for row in candidates:
            upload_id = int(row["id"])
            with _JOBS_LOCK:
                if _JOBS.get(upload_id, {}).get("berjalan"):
                    continue
                # Klaim atomik (UPDATE ... WHERE status = status lama) supaya klik ganda / dua tab
                # tidak mengekstrak file yang sama dua kali.
                with self.engine.begin() as conn:
                    result = conn.execute(text("""
                        UPDATE akreditasi_upload_file SET status = 'sedang_diekstrak'
                        WHERE id = :id AND status = :lama
                    """), {"id": upload_id, "lama": row["status"]})
                if result.rowcount != 1:
                    continue
                _JOBS[upload_id] = {"berjalan": True, "batch": 0, "total": 0, "ringkasan": None}
            claimed.append(upload_id)
        if claimed:
            if background:
                threading.Thread(target=self._run_extraction, args=(claimed, dict(laporan)), daemon=True).start()
            else:
                self._run_extraction(claimed, dict(laporan))
        return {"dimulai": len(claimed)}

    def _run_extraction(self, upload_ids: list[int], laporan: dict[str, Any]) -> None:
        lap_id = int(laporan["id"])
        for upload_id in upload_ids:
            ringkasan: dict[str, Any]
            try:
                with self.engine.connect() as conn:
                    row = conn.execute(text("""
                        SELECT path_lokal, tipe_file, nama_file FROM akreditasi_upload_file WHERE id = :id
                    """), {"id": upload_id}).mappings().one()

                def progress(batch: int, total: int, _id: int = upload_id) -> None:
                    with _JOBS_LOCK:
                        _JOBS[_id].update(batch=batch, total=total)

                rows, ringkasan = self.extractor(row["path_lokal"], row["tipe_file"], laporan["dokumen"], progress)
                now = datetime.now()
                with self.engine.begin() as conn:
                    # Ulang ekstraksi file yang sama: riwayat nilai lama file ini diganti; data laporan
                    # yang sudah terisi tetap (nilai yang sama akan tercatat "sudah_ada").
                    conn.execute(text("DELETE FROM akreditasi_upload_ekstraksi WHERE upload_file_id = :id"),
                                 {"id": upload_id})
                    if rows:
                        conn.execute(text("""
                            INSERT INTO akreditasi_upload_ekstraksi
                              (upload_file_id, prodi_id, laporan_id, item_id, baris_ke, nama_kolom, nilai, kutipan, created_at)
                            VALUES (:upload_file_id, :prodi_id, :laporan_id, :item_id, :baris_ke, :nama_kolom, :nilai, :kutipan, :created_at)
                        """), [{**r, "upload_file_id": upload_id, "prodi_id": laporan["prodi_id"], "laporan_id": lap_id,
                                "created_at": now} for r in rows])
                        baru = [dict(r) for r in conn.execute(text("""
                            SELECT id, item_id, baris_ke, nama_kolom, nilai FROM akreditasi_upload_ekstraksi
                            WHERE upload_file_id = :id ORDER BY id
                        """), {"id": upload_id}).mappings().all()]
                        ringkasan = {**ringkasan, "diterapkan": terapkan_ekstraksi(conn, laporan, baru, row["nama_file"], now)}
                    # "gagal" hanya bila SEMUA batch gagal / teks tak terbaca; parsial tetap "diekstrak".
                    gagal = not rows and (ringkasan.get("n_batch", 0) == 0 or
                                          ringkasan.get("n_batch_gagal", 0) >= ringkasan.get("n_batch", 0))
                    conn.execute(text("""
                        UPDATE akreditasi_upload_file SET status = :s, diekstrak_at = :t WHERE id = :id
                    """), {"s": "gagal_ekstrak" if gagal else "diekstrak", "t": now, "id": upload_id})
            except Exception as exc:  # noqa: BLE001 -- apa pun penyebabnya, file harus keluar dari "sedang"
                logger.exception("ekstraksi upload %s gagal", upload_id)
                ringkasan = {"error": f"Ekstraksi gagal: {exc}"}
                try:
                    with self.engine.begin() as conn:
                        conn.execute(text("""
                            UPDATE akreditasi_upload_file SET status = 'gagal_ekstrak', diekstrak_at = :t WHERE id = :id
                        """), {"t": datetime.now(), "id": upload_id})
                except Exception:  # noqa: BLE001
                    logger.exception("status upload %s tidak bisa diperbarui", upload_id)
            with _JOBS_LOCK:
                _JOBS[upload_id] = {"berjalan": False, "batch": 0, "total": 0, "ringkasan": ringkasan}
