"""Pipeline live: tarik daftar publikasi Scopus (10 terbaru/dosen, sesuai
batasan halaman profil SINTA -- lihat docstring parse_scopus_docs) untuk
18 DTPR Prodi MEI dari sinta.kemdiktisaintek.go.id, simpan ke tabel
akreditasi_publikasi_dosen.

Sumber data ini melengkapi kolom yang TIDAK BISA dipenuhi live: gap
"metrik publikasi" di lkps_3_a_2 (lihat akreditasi/data_source_map.json,
field sumber_tambahan) -- BUKAN pengganti data hibah/nominal/mahasiswa
terlibat yang tetap tidak_tersedia (SIMASTER modul Penelitian login-gated).

Pola arsitektur SAMA dengan berita-dampak/scripts/ingest.py: requests
biasa (BUKAN headless browser -- sudah divalidasi server-render HTML
polos, tidak butuh JS), db.upsert() (INSERT ... ON DUPLICATE KEY UPDATE,
kunci = link Scopus per publikasi) supaya AKUMULATIF antar run -- bukan
truncate/replace, sehingga cakupan historis bertambah alami dari waktu ke
waktu walau tiap fetch cuma menangkap 10 publikasi terbaru per dosen.

Roster 18 DTPR (nama + sinta_id) di bawah adalah data statis yang jarang
berubah -- diverifikasi manual dari halaman publik dcse.fmipa.ugm.ac.id/
mei/mei-dosen + profil individu tiap dosen (2026-09). Update manual kalau
ada DTPR baru/keluar.

Jalankan:
    ..\\venv\\Scripts\\python.exe scripts\\pipeline_sinta.py
"""
import re
import sys
import time
from datetime import datetime
from html import unescape
from pathlib import Path

import requests

sys.path.insert(0, str(Path(__file__).resolve().parent))

import db  # noqa: E402

HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
                  "(KHTML, like Gecko) Chrome/126.0 Safari/537.36"
}
REQUEST_DELAY_SEC = 2  # jeda antar dosen -- sopan ke server, bukan diam-diam dihajar 18x beruntun
TABLE = db.t("publikasi_dosen")
COLUMNS = ["link", "dosen", "sinta_id", "platform", "judul", "tahun", "sumber", "fetched_at"]

# nama, sinta_id -- verifikasi asal lihat led_b5_dosen_tendik.sumber_tambahan
# di akreditasi/data_source_map.json
DTPR = [
    ("Prof. Dr. Techn. Ahmad Ashari, M.I.Kom.", "5983428"),
    ("Wahyono, S.Kom., Ph.D.", "6098296"),
    ("Dr. Andi Dharmawan, S.Si., M.Cs.", "6018445"),
    ("Dr. Danang Lelono, S.Si., M.T.", "6014407"),
    ("Dr. Agfianto Eko Putra, M.Si.", "5985361"),
    ("Dr. Mardhani Riasetiawan, SE Ak, M.T.", "43627"),
    ("Prof. Dr. Ir. Jazi Eko Istiyanto, M.Sc.", "6038092"),
    ("Prof. Dra. Sri Hartati, M.Sc., Ph.D.", "5998874"),
    ("Dr. Raden Sumiharto, S.Si., M.Kom.", "43332"),
    ("Prof. Dr. Tri Kuntoro Priyambodo, M.Sc.", "42506"),
    ("Dr. Yohanes Suyanto, M.I.Kom.", "5985305"),
    ("Prof. Drs. Agus Harjoko, M.Sc., Ph.D.", "6031957"),
    ("Dr. Dyah Aruming Tyas, S.Si.", "6773420"),
    ("Dr. techn. Aufaclav Zatu Kusuma Frisky, S.Si., M.Sc.", "6091369"),
    ("Oskar Natan, S.ST., M.Tr.T., Ph.D.", "6736922"),
    ("Muhammad Husni Santriaji, S.Si., M.T., M.S., Ph.D.", "6931237"),
    ("Nur Achmad Sulistyo Putro, S.Si., M.Cs., Ph.D.", "6705467"),
    ("Dr. Muhammad Idham Ananta Timur, S.T., M.Kom", "6113981"),
]


def parse_scopus_docs(page_html: str) -> list[tuple[str, str, str | None, str | None]]:
    """Ekstrak (link, judul, tahun, sumber) dari tiap blok `ar-list-item` di
    halaman profil SINTA (?view=scopus). Cuma menangkap publikasi yang
    dirender langsung di halaman (~10 terbaru) -- link "View more..."
    (infinite scroll/JS) SENGAJA tidak diikuti (keputusan eksplisit, lihat
    docstring modul)."""
    docs = []
    blocks = page_html.split('<div class="ar-list-item mb-5">')[1:]
    for block in blocks:
        m_link = re.search(r'<div class="ar-title">\s*<a href="([^"]+)"[^>]*>(.*?)</a>', block, re.S)
        if not m_link:
            continue
        m_src = re.search(r'class="ar-pub"[^>]*>(?:<i[^>]*></i>)?\s*(.*?)</a>', block, re.S)
        m_year = re.search(r'class="ar-year"[^>]*>(?:<i[^>]*></i>)?\s*(\d{4})\s*</a>', block, re.S)
        link = m_link.group(1).strip()
        judul = unescape(re.sub(r"\s+", " ", m_link.group(2)).strip())
        sumber = unescape(re.sub(r"\s+", " ", m_src.group(1)).strip()) if m_src else None
        tahun = m_year.group(1) if m_year else None
        docs.append((link, judul, tahun, sumber))
    return docs


def fetch_dosen(nama: str, sinta_id: str) -> list[tuple]:
    url = f"https://sinta.kemdiktisaintek.go.id/authors/profile/{sinta_id}?view=scopus"
    try:
        r = requests.get(url, timeout=30, headers=HEADERS)
        r.raise_for_status()
    except Exception as e:  # noqa: BLE001
        print(f"  GAGAL fetch {nama} ({sinta_id}): {e}")
        return []
    docs = parse_scopus_docs(r.text)
    now = datetime.now()
    return [(link, nama, sinta_id, "scopus", judul, tahun, sumber, now) for link, judul, tahun, sumber in docs]


def main() -> None:
    engine = db.get_engine()
    if not db.table_exists(engine, TABLE):
        raise SystemExit(f"Tabel {TABLE} belum ada -- jalankan dulu "
                          "scripts/migrasi_tabel_publikasi_dosen.py")

    total_saved = 0
    ringkasan = []
    for i, (nama, sinta_id) in enumerate(DTPR):
        rows = fetch_dosen(nama, sinta_id)
        if rows:
            saved = db.upsert(
                engine, TABLE, COLUMNS, rows,
                update_columns=["dosen", "platform", "judul", "tahun", "sumber", "fetched_at"],
                label=f"upsert publikasi {nama}",
            )
        else:
            saved = 0
        ringkasan.append((nama, sinta_id, len(rows), saved))
        total_saved += saved
        print(f"[{i+1}/{len(DTPR)}] {nama}: {len(rows)} publikasi diambil, {saved} tersimpan/diperbarui")
        if i < len(DTPR) - 1:
            time.sleep(REQUEST_DELAY_SEC)

    print("\n=== RINGKASAN ===")
    nol = [n for n, _, cnt, _ in ringkasan if cnt == 0]
    for nama, sinta_id, cnt, saved in ringkasan:
        tanda = " <-- 0 HASIL" if cnt == 0 else ""
        print(f"  {nama} (SINTA {sinta_id}): {cnt} publikasi{tanda}")
    print(f"\nTotal baris tersimpan/diperbarui: {total_saved}")
    if nol:
        print(f"PERINGATAN: {len(nol)} dosen dapat 0 publikasi -- cek manual apakah profil SINTA-nya "
              f"memang kosong atau ada masalah fetch/parsing: {', '.join(nol)}")

    with engine.connect() as conn:
        n_total = conn.exec_driver_sql(f"SELECT COUNT(*) FROM `{TABLE}`").scalar()
        n_dosen = conn.exec_driver_sql(f"SELECT COUNT(DISTINCT sinta_id) FROM `{TABLE}`").scalar()
    print(f"Total baris di tabel {TABLE} sekarang: {n_total} (dari {n_dosen} dosen berbeda)")


if __name__ == "__main__":
    main()
