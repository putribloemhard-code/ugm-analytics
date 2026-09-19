from __future__ import annotations

from datetime import datetime
from pathlib import Path
from typing import Any

from sqlalchemy import text
from sqlalchemy.engine import Engine

from app.services.accreditation_auth import safe_filename

MAX_UPLOAD_BYTES = 25 * 1024 * 1024
ALLOWED_TYPES = {
    "application/pdf": "pdf",
    "application/vnd.openxmlformats-officedocument.wordprocessingml.document": "docx",
    "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet": "xlsx",
}
ALLOWED_EXTENSIONS = {".pdf": "pdf", ".docx": "docx", ".xlsx": "xlsx"}


class UploadError(ValueError):
    pass


def save_upload(engine: Engine, root: Path, prodi_id: str, filename: str, content_type: str | None, data: bytes, user_email: str) -> dict[str, Any]:
    if not prodi_id or len(prodi_id) > 64 or "/" in prodi_id or "\\" in prodi_id or ".." in prodi_id:
        raise UploadError("Program studi tidak valid.")
    if len(data) > MAX_UPLOAD_BYTES:
        raise UploadError("Ukuran file maksimal 25 MB.")
    original = Path(filename or "file").name
    ext = Path(original).suffix.lower()
    file_type = ALLOWED_TYPES.get(content_type or "") or ALLOWED_EXTENSIONS.get(ext)
    if file_type is None:
        raise UploadError("Format file harus PDF, DOCX, atau XLSX.")
    if not original or len(original) > 500:
        raise UploadError("Nama file tidak valid atau terlalu panjang.")
    safe = safe_filename(original)
    folder = (root / prodi_id).resolve()
    folder.mkdir(parents=True, exist_ok=True)
    stored = folder / f"{datetime.now():%Y%m%d%H%M%S%f}_{safe}"
    stored.write_bytes(data)
    now = datetime.now()
    try:
        with engine.begin() as conn:
            row = conn.execute(text("""
                INSERT INTO akreditasi_upload_file
                  (prodi_id, nama_file, path_lokal, tipe_file, ukuran_bytes, status, diupload_oleh, uploaded_at)
                VALUES (:prodi, :name, :path, :type, :size, 'belum_diekstrak', :user, :now)
                RETURNING id, prodi_id, nama_file, tipe_file, ukuran_bytes, status, uploaded_at, diekstrak_at
            """), {"prodi": prodi_id, "name": original, "path": str(stored), "type": file_type, "size": len(data), "user": user_email, "now": now}).mappings().one()
    except Exception:
        stored.unlink(missing_ok=True)
        raise
    return dict(row)
