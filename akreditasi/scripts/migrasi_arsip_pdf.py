"""Migrasi satu kali: pindahkan seluruh isi `akreditasi_data_manual` (hasil
ekstraksi PDF LED/LKPS lama + 2 item non-resmi hasil scrape SINTA/dcse dari
sesi sebelumnya) ke tabel arsip `akreditasi_data_manual_arsip_pdf`, lalu
buat ulang `akreditasi_data_manual` kosong.

Alasan: kebijakan baru (lihat docstring registry_kebutuhan_data.py poin 7)
melarang isi/angka dari PDF lama dipakai sebagai sumber data laporan --
PDF cuma boleh jadi referensi struktur. Tabel lama diarsipkan (BUKAN
dihapus) supaya histori tetap bisa ditelusuri kalau perlu, tapi tidak lagi
dibaca oleh dashboard/generator mana pun.

Idempoten: kalau `akreditasi_data_manual_arsip_pdf` sudah ada & sudah berisi
data, script berhenti tanpa mengubah apa pun (supaya tidak menimpa arsip
kalau dijalankan dua kali).

Jalankan sekali:
    ..\\venv\\Scripts\\python.exe scripts\\migrasi_arsip_pdf.py
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

import db  # noqa: E402

ARSIP_TABLE = db.t("data_manual_arsip_pdf")
LIVE_TABLE = db.t("data_manual")


def main() -> None:
    engine = db.get_engine()

    if db.table_exists(engine, ARSIP_TABLE):
        def _count_arsip():
            with engine.connect() as conn:
                return conn.exec_driver_sql(f"SELECT COUNT(*) FROM `{ARSIP_TABLE}`").scalar()

        ok, n = db.with_retry(_count_arsip, label="cek isi tabel arsip")
        if ok and n and n > 0:
            print(f"SKIP -- {ARSIP_TABLE} sudah ada & berisi {n} baris. Tidak ada yang diubah "
                  "(idempoten -- hapus manual dulu kalau memang mau migrasi ulang dari nol).")
            return

    if not db.table_exists(engine, LIVE_TABLE):
        print(f"SKIP -- {LIVE_TABLE} tidak ada, tidak ada yang perlu diarsipkan.")
        return

    def _count_live():
        with engine.connect() as conn:
            return conn.exec_driver_sql(f"SELECT COUNT(*) FROM `{LIVE_TABLE}`").scalar()

    ok, n_live = db.with_retry(_count_live, label="cek isi tabel live")
    if not ok:
        raise SystemExit("Gagal cek isi tabel live -- batal.")

    def _migrate():
        with engine.begin() as conn:
            conn.exec_driver_sql(f"RENAME TABLE `{LIVE_TABLE}` TO `{ARSIP_TABLE}`")

    ok, _ = db.with_retry(_migrate, label=f"RENAME {LIVE_TABLE} -> {ARSIP_TABLE}")
    if not ok:
        raise SystemExit("Gagal rename tabel -- batal.")
    print(f"OK -- {n_live} baris dipindah dari `{LIVE_TABLE}` ke `{ARSIP_TABLE}`.")

    # Buat ulang tabel live kosong (skema sama persis dgn migrasi_tabel_akreditasi.py)
    # supaya dashboard lama tidak crash -- akan tampil kosong/semua "perlu_input_manual"
    # sampai Fase 2/3 mengisi lewat tabel baru (akreditasi_publikasi_dosen dkk.), BUKAN
    # lewat pola EAV akreditasi_data_manual lagi.
    ddl = f"""
    CREATE TABLE IF NOT EXISTS `{LIVE_TABLE}` (
        id INT AUTO_INCREMENT PRIMARY KEY,
        prodi_id VARCHAR(64) NOT NULL DEFAULT 'mei',
        item_id VARCHAR(64) NOT NULL,
        baris_ke INT NOT NULL DEFAULT 1,
        kolom VARCHAR(255) NOT NULL,
        tahun VARCHAR(16) NULL,
        nilai TEXT,
        link_bukti VARCHAR(1000),
        diisi_oleh VARCHAR(255),
        updated_at DATETIME,
        UNIQUE KEY uq_prodi_item_row_col_tahun (prodi_id, item_id, baris_ke, kolom, tahun)
    ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4
    """

    def _recreate():
        with engine.begin() as conn:
            conn.exec_driver_sql(ddl)

    ok, _ = db.with_retry(_recreate, label=f"buat ulang {LIVE_TABLE} kosong")
    if not ok:
        raise SystemExit(f"GAGAL buat ulang {LIVE_TABLE} -- arsip sudah jalan tapi tabel live "
                          "belum ada, jalankan scripts/migrasi_tabel_akreditasi.py manual.")
    print(f"OK -- `{LIVE_TABLE}` dibuat ulang kosong.")


if __name__ == "__main__":
    main()
