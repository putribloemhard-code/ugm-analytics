"""Ruang kerja akreditasi: isi data LED/LKPS per item, review ekstraksi AI, generate Word.

Padanan dashboard Streamlit lama (akreditasi/scripts/dashboard_render.py,
upload_akreditasi.py, ekstraksi_akreditasi.py bagian DB, page_akreditasi.py) -- sekarang
jalur satu-satunya. Aturan yang dipertahankan persis:

- Data resmi = akreditasi_data_manual (skema long/EAV: satu baris = satu sel). Simpan satu
  item = hapus semua sel item itu untuk prodi tsb lalu tulis ulang (seperti tombol Simpan lama).
- Item berstatus "belum_tersedia" tidak bisa diisi.
- Hasil ekstraksi AI (akreditasi_upload_ekstraksi) hanya PREVIEW: mengisi sel yang MASIH
  KOSONG di draft, tidak menimpa data manual, dan sel yang punya >1 nilai berbeda antar file
  (konflik) dibiarkan kosong -- user memilih sendiri. Baru tercatat sebagai data resmi saat
  user menyimpan item itu; saat itu juga baris ekstraksinya ditandai dikonfirmasi.
- Generate Word memakai builder di akreditasi/scripts/generate_template.py dan dicatat di
  akreditasi_riwayat_generate (file disimpan supaya bisa diunduh ulang dari Profil).

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

logger = logging.getLogger(__name__)

DOKUMEN = ("LED", "LKPS")
JENJANG = ("Sarjana", "Magister", "Doktor", "Profesi", "Spesialis")
MAX_ROWS_PER_ITEM = 500
MAX_VALUE_CHARS = 20_000

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


def _validate_dokumen(dokumen: str) -> str:
    if dokumen not in DOKUMEN:
        raise WorkspaceError("Dokumen harus LED atau LKPS.")
    return dokumen


def _in_clause(prefix: str, values: list[Any]) -> tuple[str, dict[str, Any]]:
    params = {f"{prefix}{i}": value for i, value in enumerate(values)}
    return ", ".join(f":{name}" for name in params), params


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

    def workspace(self, prodi_id: str, dokumen: str) -> dict[str, Any]:
        _validate_dokumen(dokumen)
        registry = _registry()
        with self.engine.connect() as conn:
            program = self._program(conn, prodi_id)
            manual = conn.execute(text("""
                SELECT item_id, baris_ke, kolom, nilai, diisi_oleh, updated_at
                FROM akreditasi_data_manual WHERE prodi_id = :p
            """), {"p": prodi_id}).mappings().all()
            pending = conn.execute(text("""
                SELECT e.id, e.item_id, e.baris_ke, e.nama_kolom, e.nilai, e.kutipan, f.nama_file
                FROM akreditasi_upload_ekstraksi e
                JOIN akreditasi_upload_file f ON f.id = e.upload_file_id
                WHERE e.prodi_id = :p AND e.dikonfirmasi_at IS NULL
                ORDER BY e.item_id, e.baris_ke, e.nama_kolom, e.id
            """), {"p": prodi_id}).mappings().all()
            uploads = conn.execute(text("""
                SELECT id, nama_file, tipe_file, ukuran_bytes, status, diupload_oleh, uploaded_at, diekstrak_at
                FROM akreditasi_upload_file WHERE prodi_id = :p ORDER BY uploaded_at DESC, id DESC
            """), {"p": prodi_id}).mappings().all()

        manual_by_item: dict[str, list[dict]] = {}
        for row in manual:
            manual_by_item.setdefault(row["item_id"], []).append(dict(row))
        pending_by_item: dict[str, list[dict]] = {}
        for row in pending:
            pending_by_item.setdefault(row["item_id"], []).append(dict(row))
        filled_ids = set(manual_by_item)

        grouped = registry.led_items_by_kriteria() if dokumen == "LED" else registry.lkps_items_by_bagian()
        labels = registry.LABEL_KRITERIA if dokumen == "LED" else registry.LABEL_BAGIAN_LKPS
        groups = []
        for key, items in grouped.items():
            group = {
                "key": key,
                "label": labels.get(key, key),
                "items": [self._item_payload(registry, item, manual_by_item.get(item["id"], []),
                                             pending_by_item.get(item["id"], []))
                          for item in items],
                "cuplikan": [],
            }
            if dokumen == "LED" and key not in ("Umum", "D"):
                group["cuplikan"] = [
                    {"id": c["id"], "tabel_lkps": c["tabel_lkps"], "nama": c["nama"],
                     "status": c["status_ketersediaan"], "terisi": c["id"] in filled_ids}
                    for c in registry.lkps_cuplikan_untuk_kriteria(key)
                ]
            groups.append(group)

        item_ids = [item["id"] for items in grouped.values() for item in items]
        ringkasan = registry.ringkasan_status(item_ids=item_ids, terisi_ids=filled_ids)
        ringkasan["persen"] = round(100 * ringkasan["lengkap"] / ringkasan["total"]) if ringkasan["total"] else 0
        item_set = set(item_ids)
        return {
            "prodi": program,
            "dokumen": dokumen,
            "ringkasan": ringkasan,
            "groups": groups,
            "uploads": [self._upload_payload(dict(row)) for row in uploads],
            "ekstraksi": {
                "tersedia": extraction_available(),
                "item_menunggu_review": len({r["item_id"] for r in pending if r["item_id"] in item_set}),
            },
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
    def _item_payload(registry, item: dict, manual: list[dict], pending: list[dict]) -> dict[str, Any]:
        kolom = list(item["kolom_dibutuhkan"])
        status = item["status_ketersediaan"]
        terisi = bool(manual)
        if status == "tersedia_otomatis":
            state = "otomatis"
        elif status == "perlu_input_manual":
            state = "terisi" if terisi else "kosong"
        else:
            state = "belum_tersedia"

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
            "draft": _draft(kolom, rows, pending) if pending else None,
        }

    # ------------------------------------------------------------------ tulis
    def save_item(self, prodi_id: str, item_id: str, rows: Any, ekstraksi_ids: Any, user_email: str) -> dict[str, Any]:
        registry = _registry()
        item = registry.KEBUTUHAN_DATA.get(item_id)
        if not item:
            raise NotFound("Item kebutuhan data tidak dikenal.")
        if item["status_ketersediaan"] == "belum_tersedia":
            raise WorkspaceError("Item ini belum bisa diisi (status belum tersedia).")
        if not isinstance(rows, list) or not all(isinstance(r, dict) for r in rows):
            raise WorkspaceError("Format baris tidak valid.")
        if len(rows) > MAX_ROWS_PER_ITEM:
            raise WorkspaceError(f"Maksimal {MAX_ROWS_PER_ITEM} baris per item.")
        if item["tipe"] == "narasi":
            rows = rows[:1]
        try:
            ids = [int(x) for x in (ekstraksi_ids or [])]
        except (TypeError, ValueError) as exc:
            raise WorkspaceError("Daftar ekstraksi tidak valid.") from exc

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
                cells.append({"prodi_id": prodi_id, "item_id": item_id, "baris_ke": baris_ke, "kolom": k,
                              "nilai": v, "diisi_oleh": user_email, "updated_at": now})

        with self.engine.begin() as conn:
            self._program(conn, prodi_id)
            conn.execute(text("DELETE FROM akreditasi_data_manual WHERE prodi_id = :p AND item_id = :i"),
                         {"p": prodi_id, "i": item_id})
            if cells:
                conn.execute(text("""
                    INSERT INTO akreditasi_data_manual
                      (prodi_id, item_id, baris_ke, kolom, tahun, nilai, link_bukti, diisi_oleh, updated_at)
                    VALUES (:prodi_id, :item_id, :baris_ke, :kolom, NULL, :nilai, NULL, :diisi_oleh, :updated_at)
                """), cells)
            if ids:
                placeholders, params = _in_clause("e", ids)
                conn.execute(text(f"""
                    UPDATE akreditasi_upload_ekstraksi SET dikonfirmasi_at = :now
                    WHERE id IN ({placeholders}) AND prodi_id = :p AND item_id = :i AND dikonfirmasi_at IS NULL
                """), {**params, "now": now, "p": prodi_id, "i": item_id})
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
    def generate(self, prodi_id: str, dokumen: str, user_email: str) -> tuple[bytes, str]:
        _validate_dokumen(dokumen)
        if self.generated_root is None:
            raise RuntimeError("Folder dokumen hasil generate belum dikonfigurasi.")
        with self.engine.connect() as conn:
            self._program(conn, prodi_id)
            df = pd.read_sql(text("""
                SELECT item_id, baris_ke, kolom, tahun, nilai, link_bukti
                FROM akreditasi_data_manual WHERE prodi_id = :p
            """), conn, params={"p": prodi_id})
        generator = load_accreditation_module("generate_template.py")
        content = generator.build_led_docx(df) if dokumen == "LED" else generator.build_lkps_docx(df)

        now = datetime.now()
        folder = (self.generated_root / re.sub(r"[^A-Za-z0-9_-]", "_", prodi_id)).resolve()
        folder.mkdir(parents=True, exist_ok=True)
        path = folder / f"{now:%Y%m%d_%H%M%S_%f}_{dokumen}.docx"
        path.write_bytes(content)
        try:
            with self.engine.begin() as conn:
                conn.execute(text("""
                    INSERT INTO akreditasi_riwayat_generate (user_email, prodi_id, jenis_dokumen, file_path, generated_at)
                    VALUES (:e, :p, :j, :f, :t)
                """), {"e": user_email, "p": prodi_id, "j": dokumen, "f": str(path), "t": now})
        except Exception:
            path.unlink(missing_ok=True)  # jangan tinggalkan file yatim
            raise
        return content, f"Laporan_Akreditasi_{dokumen}_{prodi_id}_{now:%Y%m%d}.docx"

    def history_file(self, riwayat_id: int, user_email: str) -> tuple[bytes, str]:
        """File riwayat milik user sendiri. Path berasal dari DB, tetap dicek berada di folder generate."""
        with self.engine.connect() as conn:
            row = conn.execute(text("""
                SELECT prodi_id, jenis_dokumen, file_path, generated_at FROM akreditasi_riwayat_generate
                WHERE id = :id AND user_email = :e
            """), {"id": riwayat_id, "e": user_email}).mappings().first()
        if not row or self.generated_root is None:
            raise NotFound("Riwayat tidak ditemukan.")
        path = Path(row["file_path"]).resolve()
        if not path.is_relative_to(self.generated_root.resolve()) or not path.is_file():
            raise NotFound("Berkas laporan ini sudah tidak tersedia di server.")
        stamp = str(row["generated_at"] or "")[:10].replace("-", "")
        return path.read_bytes(), f"Laporan_Akreditasi_{row['jenis_dokumen']}_{row['prodi_id']}_{stamp}.docx"

    # ------------------------------------------------------------------ ekstraksi AI
    def start_extraction(self, prodi_id: str, dokumen: str, background: bool = True) -> dict[str, Any]:
        _validate_dokumen(dokumen)
        if not extraction_available():
            raise WorkspaceError("Ekstraksi AI belum dikonfigurasi (OPENAI_API_KEY kosong di .env).")
        with self.engine.connect() as conn:
            self._program(conn, prodi_id)
            candidates = conn.execute(text("""
                SELECT id, status FROM akreditasi_upload_file
                WHERE prodi_id = :p AND status IN ('belum_diekstrak', 'gagal_ekstrak', 'sedang_diekstrak')
                ORDER BY uploaded_at, id
            """), {"p": prodi_id}).mappings().all()
        claimed: list[int] = []
        for row in candidates:
            upload_id = int(row["id"])
            with _JOBS_LOCK:
                if _JOBS.get(upload_id, {}).get("berjalan"):
                    continue
                # Klaim atomik (UPDATE ... WHERE status = status lama) supaya klik ganda / dua tab
                # tidak mengekstrak file yang sama dua kali (duplikat baris -> konflik palsu).
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
                threading.Thread(target=self._run_extraction, args=(claimed, prodi_id, dokumen), daemon=True).start()
            else:
                self._run_extraction(claimed, prodi_id, dokumen)
        return {"dimulai": len(claimed)}

    def _run_extraction(self, upload_ids: list[int], prodi_id: str, dokumen: str) -> None:
        for upload_id in upload_ids:
            ringkasan: dict[str, Any]
            try:
                with self.engine.connect() as conn:
                    row = conn.execute(text("""
                        SELECT path_lokal, tipe_file FROM akreditasi_upload_file WHERE id = :id
                    """), {"id": upload_id}).mappings().one()

                def progress(batch: int, total: int, _id: int = upload_id) -> None:
                    with _JOBS_LOCK:
                        _JOBS[_id].update(batch=batch, total=total)

                rows, ringkasan = self.extractor(row["path_lokal"], row["tipe_file"], dokumen, progress)
                now = datetime.now()
                with self.engine.begin() as conn:
                    # Ulang ekstraksi file yang sama: buang preview lama yang belum direview.
                    conn.execute(text("""
                        DELETE FROM akreditasi_upload_ekstraksi WHERE upload_file_id = :id AND dikonfirmasi_at IS NULL
                    """), {"id": upload_id})
                    if rows:
                        conn.execute(text("""
                            INSERT INTO akreditasi_upload_ekstraksi
                              (upload_file_id, prodi_id, item_id, baris_ke, nama_kolom, nilai, kutipan, created_at)
                            VALUES (:upload_file_id, :prodi_id, :item_id, :baris_ke, :nama_kolom, :nilai, :kutipan, :created_at)
                        """), [{**r, "upload_file_id": upload_id, "prodi_id": prodi_id, "created_at": now} for r in rows])
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


def _draft(kolom: list[str], rows: list[dict[str, str]], pending: list[dict]) -> dict[str, Any]:
    """Gabungkan hasil ekstraksi AI yang belum direview ke salinan baris manual.

    - sel kosong + satu nilai AI  -> diisi, dicatat di `ai_cells` (ditandai di UI + kutipan)
    - sel sudah berisi data manual -> TIDAK ditimpa, dicatat di `skipped`
    - >1 nilai berbeda antar file   -> dibiarkan kosong, semua opsi di `conflicts`
    `ekstraksi_ids` = semua baris ekstraksi item ini; dikirim balik saat Simpan supaya ditandai
    selesai direview (dipakai atau tidak).
    """
    draft_rows = [dict(r) for r in rows]
    manual_filled = {(i + 1, k) for i, r in enumerate(rows) for k, v in r.items() if str(v).strip()}
    grouped: dict[tuple[int, str], list[dict]] = {}
    for r in pending:
        grouped.setdefault((int(r["baris_ke"]), r["nama_kolom"]), []).append(r)
    ai_cells, conflicts, skipped = [], [], []
    for (baris_ke, nama_kolom), grp in sorted(grouped.items()):
        if nama_kolom not in kolom:
            continue
        # Baris disiapkan juga untuk konflik (sel tetap kosong) supaya user punya tempat memilih opsinya.
        while len(draft_rows) < baris_ke:
            draft_rows.append({k: "" for k in kolom})
        if len({g["nilai"] for g in grp}) > 1:
            conflicts.append({"baris_ke": baris_ke, "kolom": nama_kolom,
                              "opsi": [{"nilai": g["nilai"], "nama_file": g["nama_file"], "kutipan": g["kutipan"]}
                                       for g in grp]})
            continue
        first = grp[0]
        sumber = {"baris_ke": baris_ke, "kolom": nama_kolom, "nilai": first["nilai"],
                  "kutipan": first["kutipan"], "nama_file": first["nama_file"]}
        if (baris_ke, nama_kolom) in manual_filled:
            skipped.append(sumber)
            continue
        draft_rows[baris_ke - 1][nama_kolom] = first["nilai"]
        ai_cells.append(sumber)
    return {"rows": draft_rows, "ai_cells": ai_cells, "conflicts": conflicts, "skipped": skipped,
            "ekstraksi_ids": [int(r["id"]) for r in pending]}
