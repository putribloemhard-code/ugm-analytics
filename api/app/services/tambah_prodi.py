"""Tambah daftar program studi per fakultas ke portal Akreditasi (padanan "+ Tambah prodi baru").

Memakai AccreditationWorkspaceService.add_program, jadi aturan nama, jenjang, dan slug sama persis
dengan form di /akreditasi. Prodi yang namanya sudah ada di fakultas itu dilewati, jadi aman diulang.

    # server (container api, PostgreSQL)
    docker compose run --rm --entrypoint python api -m app.services.tambah_prodi
    # lokal (MySQL dari .env di root repo), dari folder api/
    python -m app.services.tambah_prodi --mysql-lokal
"""
from __future__ import annotations

import argparse

from sqlalchemy import text

from app.services.accreditation_workspace import AccreditationWorkspaceService, WorkspaceError

# slug fakultas (akreditasi_fakultas.slug) -> [(nama prodi, jenjang)]. Penamaan mengikuti prodi yang
# sudah ada: Sarjana tanpa awalan jenjang, Magister/Doktor dengan awalan.
PRODI: dict[str, list[tuple[str, str]]] = {
    "ftp": [  # Fakultas Teknologi Pertanian (ditambahkan 2026-10-07)
        ("Teknologi Pangan dan Produk Pertanian", "Sarjana"),
        ("Teknik Pertanian", "Sarjana"),
        ("Teknologi Industri Pertanian", "Sarjana"),
        ("Magister Ilmu dan Teknologi Pangan", "Magister"),
        ("Magister Teknologi Hasil Perkebunan", "Magister"),
        ("Magister Teknik Pertanian", "Magister"),
        ("Magister Teknologi Industri Pertanian", "Magister"),
        ("Doktor Ilmu Pangan", "Doktor"),
        ("Doktor Ilmu Teknik Pertanian", "Doktor"),
        ("Doktor Teknologi Industri Pertanian", "Doktor"),
    ],
}


def tambah(engine) -> list[tuple[str, str, str]]:
    """Tambahkan semua PRODI; kembalikan [(fakultas, nama, hasil)] dengan hasil = slug baru / 'sudah ada'."""
    svc = AccreditationWorkspaceService(engine)
    hasil = []
    for slug_fakultas, daftar in PRODI.items():
        with engine.connect() as conn:
            fakultas_id = conn.execute(text("SELECT id FROM akreditasi_fakultas WHERE slug = :s"),
                                       {"s": slug_fakultas}).scalar()
        if fakultas_id is None:
            raise SystemExit(f"Fakultas dengan slug '{slug_fakultas}' tidak ada di akreditasi_fakultas.")
        for nama, jenjang in daftar:
            try:
                hasil.append((slug_fakultas, nama, svc.add_program(fakultas_id, nama, jenjang)["slug"]))
            except WorkspaceError as exc:
                if "sudah ada" not in str(exc):
                    raise
                hasil.append((slug_fakultas, nama, "sudah ada"))
    return hasil


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--mysql-lokal", action="store_true", help="pakai MySQL dari .env root repo (mode laptop)")
    args = parser.parse_args()
    if args.mysql_lokal:
        from app.services.migrasi_kolom_tabel import _engine_mysql_lokal
        engine = _engine_mysql_lokal()
    else:
        from app.db import get_engine
        engine = get_engine()
    for fakultas, nama, slug in tambah(engine):
        print(f"  [{fakultas}] {nama}: {slug}")


if __name__ == "__main__":
    main()
