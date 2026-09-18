from __future__ import annotations

from typing import Any

import pandas as pd
from sqlalchemy import text
from sqlalchemy.engine import Engine


class AccreditationService:
    """Read-only projection of the migrated accreditation catalog."""

    def __init__(self, engine: Engine):
        self.engine = engine

    def _read(self, sql: str, params: dict[str, Any] | None = None) -> pd.DataFrame:
        return pd.read_sql(text(sql), self.engine, params=params or {})

    def summary(self) -> dict[str, Any]:
        row = self._read(
            """
            SELECT
              (SELECT COUNT(*) FROM akreditasi_fakultas) AS fakultas,
              (SELECT COUNT(*) FROM akreditasi_prodi) AS prodi,
              (SELECT COUNT(*) FROM akreditasi_item_tersedia) AS item_tersedia,
              (SELECT COUNT(*) FROM akreditasi_data_manual) AS data_manual,
              (SELECT COUNT(*) FROM akreditasi_publikasi_dosen) AS publikasi_dosen,
              (SELECT COUNT(*) FROM akreditasi_upload_file) AS upload_file
            """
        ).iloc[0]
        return {key: int(row[key]) for key in row.index}

    def requirements(self) -> dict[str, Any]:
        from app.domain.source import load_accreditation_module
        registry = load_accreditation_module("registry_kebutuhan_data.py")
        led = registry.led_items_by_kriteria()
        lkps = registry.lkps_items_by_bagian()
        def flatten(grouped: dict[str, list[dict[str, Any]]]) -> list[dict[str, Any]]:
            rows = []
            for group, items in grouped.items():
                for item in items:
                    rows.append({
                        "id": item["id"], "group": group, "name": item["nama"],
                        "type": item.get("tipe", ""), "status": item.get("status_ketersediaan", ""),
                        "description": item.get("deskripsi_singkat", ""),
                        "columns": item.get("kolom_dibutuhkan", []),
                    })
            return rows
        return {"led": flatten(led), "lkps": flatten(lkps)}

    def catalog(self) -> dict[str, Any]:
        faculties = self._read(
            "SELECT id, nama, slug, url FROM akreditasi_fakultas ORDER BY nama"
        ).fillna("").to_dict(orient="records")
        programs = self._read(
            """
            SELECT p.id, p.fakultas_id, f.nama AS fakultas, p.nama, p.jenjang, p.slug, p.url
            FROM akreditasi_prodi p
            LEFT JOIN akreditasi_fakultas f ON f.id = p.fakultas_id
            ORDER BY f.nama, p.nama
            """
        ).fillna("").to_dict(orient="records")
        manual = self._read(
            """
            SELECT id, prodi_id, item_id, baris_ke, kolom, tahun, nilai,
                   link_bukti, updated_at
            FROM akreditasi_data_manual
            ORDER BY updated_at DESC NULLS LAST, id DESC
            LIMIT 100
            """
        ).fillna("").to_dict(orient="records")
        publications = self._read(
            """
            SELECT link, dosen, sinta_id, platform, judul, tahun, sumber, fetched_at
            FROM akreditasi_publikasi_dosen
            ORDER BY tahun DESC NULLS LAST, fetched_at DESC NULLS LAST
            LIMIT 100
            """
        ).fillna("").to_dict(orient="records")
        uploads = self._read(
            """
            SELECT id, prodi_id, nama_file, tipe_file, ukuran_bytes, status,
                   uploaded_at, diekstrak_at
            FROM akreditasi_upload_file
            ORDER BY uploaded_at DESC NULLS LAST, id DESC
            LIMIT 100
            """
        ).fillna("").to_dict(orient="records")
        return {"faculties": faculties, "programs": programs, "manual": manual,
                "publications": publications, "uploads": uploads}

    def full_read_model(self) -> dict[str, Any]:
        return {"summary": self.summary(), **self.catalog(), "requirements": self.requirements()}
