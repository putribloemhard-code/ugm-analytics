"""Migrasi sekali jalan: isian tabel akreditasi ke nama kolom format Excel (akreditasi/format_tabel.json).

Sejak 2026-10-06 kolom isian tabel = kolom template Excel resmi. Isian yang tersimpan dengan nama
kolom lama dipindah ke nama baru memakai `kolom_lama` di format_tabel.json. Tidak ada isian tim yang
dihapus: sel yang kolom lamanya tidak punya padanan dipindah ke tabel arsip
`akreditasi_data_manual_arsip_kolom` (struktur sama dengan akreditasi_data_manual).

Yang disentuh:
- akreditasi_data_manual      : ganti nama kolom; sel tanpa padanan -> arsip
- akreditasi_item_tersedia    : ganti nama kolom data live (bisa ditarik ulang pipeline)
- akreditasi_upload_ekstraksi : ganti nama kolom riwayat ekstraksi AI
- Tabel 6 (visi): baris per level (PT/UPPS/PS) diputar jadi satu baris Visi PT | Visi UPPS |
  Visi Keilmuan PS; teks misi tidak punya kolom di format resmi -> arsip (data live: dihapus,
  pipeline menulis format baru).

Aman diulang (idempoten). Bawaan hanya melaporkan; tambahkan --terapkan untuk mengubah data.

    # server (container api, PostgreSQL)
    docker compose run --rm --entrypoint python api -m app.services.migrasi_kolom_tabel [--terapkan]
    # lokal (MySQL dari .env di root repo), dari folder api/
    python -m app.services.migrasi_kolom_tabel --mysql-lokal [--terapkan]
"""
from __future__ import annotations

import argparse
import os
from pathlib import Path

from sqlalchemy import URL, bindparam, create_engine, inspect, text
from sqlalchemy.engine import Connection, Engine

from app.domain.source import load_accreditation_module

ARSIP = "akreditasi_data_manual_arsip_kolom"
MANUAL, LIVE, EKSTRAKSI = "akreditasi_data_manual", "akreditasi_item_tersedia", "akreditasi_upload_ekstraksi"
VISI = {"PT": "Visi PT", "UPPS": "Visi UPPS", "PS": "Visi Keilmuan PS"}
KOLOM_LEVEL, KOLOM_VISI = "Level (PT/UPPS/PS)", "Teks Visi"


def _sql(teks: str):
    """text() dengan parameter :k sebagai daftar (IN :k)."""
    q = text(teks)
    return q.bindparams(bindparam("k", expanding=True)) if ":k" in teks else q


# Kolom lama berisi pilihan "TS-2"/"TS-1"/"TS" -> format resmi memberi tanda √ di kolom tahunnya.
TANDA_TAHUN = {
    "lkps_3_c_2": ("Tahun Terbit (TS-2/TS-1/TS)", "Tahun Terbit (beri tanda √)"),
    "lkps_3_c_3": ("Tahun Perolehan (TS-2/TS-1/TS)", "Tahun Perolehan (beri tanda √)"),
    "lkps_4_c_3": ("Tahun Perolehan (TS-2/TS-1/TS)", "Tahun Perolehan (beri tanda √)"),
}


def _tanda_tahun(conn: Connection, terapkan: bool) -> int:
    baru = 0
    for item_id, (lama, grup) in TANDA_TAHUN.items():
        for r in [dict(x) for x in conn.execute(text(
                f"SELECT * FROM {MANUAL} WHERE item_id = :i AND kolom = :lama"), {"i": item_id, "lama": lama}).mappings()]:
            ts = (r["nilai"] or "").strip().upper().replace(" ", "")
            if ts not in ("TS-2", "TS-1", "TS"):
                continue
            kolom = f"{grup} – {ts}"
            ada = conn.execute(text(f"SELECT COUNT(*) FROM {MANUAL} WHERE item_id = :i AND laporan_id = :l "
                                    "AND baris_ke = :b AND kolom = :k"),
                               {"i": item_id, "l": r["laporan_id"], "b": r["baris_ke"], "k": kolom}).scalar()
            if ada:
                continue
            baru += 1
            if terapkan:
                isi = {k: v for k, v in r.items() if k != "id"}
                isi.update(kolom=kolom, nilai="√")
                conn.execute(text(f"INSERT INTO {MANUAL} ({', '.join(isi)}) VALUES ({', '.join(':' + k for k in isi)})"), isi)
    return baru


def _level(nilai: str) -> str | None:
    awal = (nilai or "").strip().upper()
    for kode in ("UPPS", "PT", "PS"):  # UPPS dulu: "PS"/"PT" bisa jadi awalan kata lain
        if awal.startswith(kode):
            return kode
    return None


def rencana(registry) -> dict[str, dict]:
    """item_id -> {"ganti": {lama: baru}, "kolom": [kolom baru]} untuk semua isian bertemplate."""
    hasil = {}
    for item_id, fmt in registry.FORMAT_TABEL.items():
        ganti = {lama: registry.kunci_kolom(baru) for lama, baru in fmt["kolom_lama"].items()
                 if lama != registry.kunci_kolom(baru)}
        hasil[item_id] = {"ganti": ganti, "kolom": list(registry.KEBUTUHAN_DATA[item_id]["kolom_dibutuhkan"])}
    return hasil


def _putar_visi(conn: Connection, tabel: str, per_laporan: bool, terapkan: bool) -> int:
    """Tabel 6: tiap baris (Level, Teks Visi) -> sel 'Visi PT/UPPS/Keilmuan PS' di baris 1."""
    rows = [dict(r) for r in conn.execute(_sql(
        f"SELECT * FROM {tabel} WHERE item_id = 'lkps_6' AND kolom IN :k"), {"k": [KOLOM_LEVEL, KOLOM_VISI]}).mappings()]
    kelompok: dict[object, dict[int, dict]] = {}
    for r in rows:
        laporan = r.get("laporan_id") if per_laporan else None
        kelompok.setdefault(laporan, {}).setdefault(int(r["baris_ke"]), {})[r["kolom"]] = r
    baru = 0
    for laporan, per_baris in kelompok.items():
        filter_lap, arg = (" AND laporan_id = :l", {"l": laporan}) if per_laporan else ("", {})
        sudah = set(conn.execute(_sql(f"SELECT kolom FROM {tabel} WHERE item_id = 'lkps_6' AND kolom IN :k{filter_lap}"),
                                 {"k": list(VISI.values()), **arg}).scalars())
        for sel in per_baris.values():
            level = _level((sel.get(KOLOM_LEVEL) or {}).get("nilai") or "")
            visi = sel.get(KOLOM_VISI)
            if not level or not visi or VISI[level] in sudah:
                continue
            baru += 1
            sudah.add(VISI[level])
            if terapkan:
                isi = {k: v for k, v in visi.items() if k != "id"}
                isi.update(kolom=VISI[level], baris_ke=1)
                conn.execute(text(f"INSERT INTO {tabel} ({', '.join(isi)}) VALUES ({', '.join(':' + k for k in isi)})"), isi)
    return baru


def migrasi(engine: Engine, terapkan: bool = False) -> dict[str, int]:
    registry = load_accreditation_module("registry_kebutuhan_data.py")
    plan = rencana(registry)
    tabel_ada = set(inspect(engine).get_table_names())
    punya_live, punya_ekstraksi = LIVE in tabel_ada, EKSTRAKSI in tabel_ada
    hasil = dict.fromkeys(["ganti_manual", "arsip_manual", "ganti_live", "ganti_ekstraksi",
                           "visi_manual", "visi_live", "hapus_live_visi", "tanda_tahun"], 0)
    with engine.connect() as conn:
        if terapkan and ARSIP not in tabel_ada:
            conn.execute(text(f"CREATE TABLE {ARSIP} AS SELECT * FROM {MANUAL} WHERE 1=0"))

        # Tabel 6 lebih dulu: butuh kolom Level + Teks Visi sebelum keduanya diarsipkan.
        hasil["visi_manual"] = _putar_visi(conn, MANUAL, True, terapkan)
        hasil["tanda_tahun"] = _tanda_tahun(conn, terapkan)
        if punya_live:
            hasil["visi_live"] = _putar_visi(conn, LIVE, False, terapkan)

        for item_id, p in plan.items():
            for lama, baru in p["ganti"].items():
                arg = {"i": item_id, "lama": lama, "baru": baru}
                target = [(MANUAL, "kolom", "ganti_manual")]
                target += [(LIVE, "kolom", "ganti_live")] if punya_live else []
                target += [(EKSTRAKSI, "nama_kolom", "ganti_ekstraksi")] if punya_ekstraksi else []
                for tabel, kol, kunci in target:
                    hasil[kunci] += conn.execute(text(
                        f"SELECT COUNT(*) FROM {tabel} WHERE item_id = :i AND {kol} = :lama"), arg).scalar() or 0
                    if terapkan:
                        conn.execute(text(f"UPDATE {tabel} SET {kol} = :baru WHERE item_id = :i AND {kol} = :lama"), arg)

            # Sel isian tim yang kolomnya tidak ada di format baru -> arsip. Saat laporan (belum
            # diganti nama), kolom lama yang punya padanan belum dihitung sebagai sisa.
            boleh = p["kolom"] + ([] if terapkan else list(p["ganti"]))
            sisa = f"FROM {MANUAL} WHERE item_id = :i AND kolom NOT IN :k"
            arg = {"i": item_id, "k": boleh}
            hasil["arsip_manual"] += conn.execute(_sql(f"SELECT COUNT(*) {sisa}"), arg).scalar() or 0
            if terapkan:
                conn.execute(_sql(f"INSERT INTO {ARSIP} SELECT * {sisa}"), arg)
                conn.execute(_sql(f"DELETE {sisa}"), arg)

        if punya_live:
            # Data live tabel 6 format lama (Level/Teks Visi/Teks Misi) ditulis ulang pipeline: hapus.
            lama_visi = f"FROM {LIVE} WHERE item_id = 'lkps_6' AND kolom NOT IN :k"
            hasil["hapus_live_visi"] = conn.execute(_sql(f"SELECT COUNT(*) {lama_visi}"), {"k": list(VISI.values())}).scalar() or 0
            if terapkan:
                conn.execute(_sql(f"DELETE {lama_visi}"), {"k": list(VISI.values())})

        if terapkan:
            conn.commit()
        else:
            conn.rollback()
    return hasil


def _engine_mysql_lokal() -> Engine:
    from dotenv import load_dotenv
    load_dotenv(Path(__file__).resolve().parents[3] / ".env")
    url = URL.create("mysql+pymysql", username=os.environ["MYSQL_USER"], password=os.environ["MYSQL_PASSWORD"],
                     host=os.environ["MYSQL_HOST"], port=int(os.environ.get("MYSQL_PORT", "3306")),
                     database=os.environ["MYSQL_DB"])
    return create_engine(url, pool_pre_ping=True)


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--terapkan", action="store_true", help="ubah data (tanpa ini hanya laporan)")
    parser.add_argument("--mysql-lokal", action="store_true", help="pakai MySQL dari .env root repo (mode laptop)")
    args = parser.parse_args()
    if args.mysql_lokal:
        engine = _engine_mysql_lokal()
    else:
        from app.db import get_engine
        engine = get_engine()
    hasil = migrasi(engine, terapkan=args.terapkan)
    mode = "DITERAPKAN" if args.terapkan else "LAPORAN SAJA (belum ada yang diubah; tambahkan --terapkan)"
    print(f"Migrasi kolom tabel akreditasi -- {mode}")
    print(f"  isian tim   : {hasil['ganti_manual']} sel ganti nama kolom, {hasil['arsip_manual']} sel tanpa padanan -> {ARSIP}")
    print(f"  tabel 6     : {hasil['visi_manual']} sel visi isian tim + {hasil['visi_live']} sel visi data live diputar")
    print(f"  tahun (√)   : {hasil['tanda_tahun']} sel 'TS-2/TS-1/TS' jadi tanda √ di kolom tahunnya (3.C.2, 3.C.3, 4.C.3)")
    print(f"  data live   : {hasil['ganti_live']} sel ganti nama kolom, {hasil['hapus_live_visi']} sel format lama tabel 6 dihapus")
    print(f"  ekstraksi AI: {hasil['ganti_ekstraksi']} riwayat ganti nama kolom")


if __name__ == "__main__":
    main()
