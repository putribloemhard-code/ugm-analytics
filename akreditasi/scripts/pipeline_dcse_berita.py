"""Pipeline live: crawl arsip berita/pengumuman dcse.fmipa.ugm.ac.id
(RSS feed resmi, BUKAN pencarian kata kunci ad-hoc) ke tabel
akreditasi_berita_dcse, sbg bukti pendukung utk gap "akses_data" di
lkps_2_d (Rekognisi Lulusan) & lkps_4_c_2 (Diseminasi Hasil PkM) --
lihat akreditasi/data_source_map.json.

KENAPA RSS, BUKAN PENCARIAN KATA KUNCI: sesi sebelumnya sempat pakai
pencarian web ad-hoc untuk cari contoh berita PkM/prestasi -- itu TIDAK
sistematis (tidak ada jaminan cakupan lengkap). RSS feed dcse.fmipa.ugm.
ac.id (WordPress standar, mendukung paginasi ?paged=N) memungkinkan crawl
SISTEMATIS: backfill mundur beberapa halaman sekali jalan, lalu tiap run
berikutnya cukup ambil halaman pertama utk menangkap post baru --
akumulatif lewat db.upsert() (url = primary key), pola identik dgn
berita-dampak/scripts/ingest.py.

CATATAN PENTING (jangan dihapus saat generate laporan Fase 3): tabel ini
menyimpan SEMUA berita departemen (lintas prodi -- S1 Elins, S1/S2/S3
Ilmu Komputer, S2 MEI, S2 Kecerdasan Artifisial), BUKAN cuma soal MEI.
Kolom `relevan_mei` menandai (bukan menyaring permanen) baris yang
menyebut frasa spesifik MEI -- SENGAJA tidak cuma cek substring "mei"
case-insensitive (itu akan match kata "Mei" nama bulan di hampir semua
tanggal artikel Indonesia, false-positive besar-besaran). Bahkan yang
`relevan_mei=1` TETAP PERLU dicek manual sebelum dipakai sbg bukti resmi
LKPS -- ini sinyal awal utk mempersempit pencarian manusia, bukan
otomasi penuh gantikan verifikasi manusia (sesuai gap lkps_2_d/4_c_2 yang
sudah ditandai "tidak_tersedia" secara sengaja, bukan "tersedia").

Jalankan (backfill awal, ambil N halaman feed pertama):
    ..\\venv\\Scripts\\python.exe scripts\\pipeline_dcse_berita.py --pages 20

Run berkala berikutnya (cukup 2-3 halaman utk tangkap post baru):
    ..\\venv\\Scripts\\python.exe scripts\\pipeline_dcse_berita.py --pages 3
"""
import argparse
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
FEED_BASE = "https://dcse.fmipa.ugm.ac.id/feed/"
REQUEST_DELAY_SEC = 1.5
TABLE = db.t("berita_dcse")
COLUMNS = ["url", "judul", "tanggal", "deskripsi", "kategori", "relevan_mei", "fetched_at"]

# Frasa spesifik MEI -- SENGAJA multi-kata, bukan substring "mei" polos
# (lihat penjelasan panjang di docstring modul: "mei" polos match nama bulan).
FRASA_MEI = [
    "magister elektronika dan instrumentasi",
    "master in electronics and instrumentation",
    "prodi mei",
    "program studi mei",
    "s2 elektronika dan instrumentasi",
]


def is_relevan_mei(judul: str, deskripsi: str, kategori: str) -> bool:
    teks = f"{judul} {deskripsi} {kategori}".lower()
    return any(frasa in teks for frasa in FRASA_MEI)


def parse_feed(xml: str) -> list[dict]:
    out = []
    for m in re.finditer(r"<item>(.*?)</item>", xml, re.S):
        body = m.group(1)
        title = re.search(r"<title>(?:<!\[CDATA\[)?(.*?)(?:\]\]>)?</title>", body, re.S)
        link = re.search(r"<link>(.*?)</link>", body, re.S)
        pub = re.search(r"<pubDate>(.*?)</pubDate>", body, re.S)
        desc = re.search(r"<description>(?:<!\[CDATA\[)?(.*?)(?:\]\]>)?</description>", body, re.S)
        cats = re.findall(r"<category>(?:<!\[CDATA\[)?(.*?)(?:\]\]>)?</category>", body, re.S)
        if not (title and link):
            continue
        d = unescape(desc.group(1)) if desc else ""
        d = re.sub(r"<[^>]+>", " ", d)
        out.append({
            "judul": unescape(title.group(1)).strip(),
            "url": link.group(1).strip(),
            "tanggal": pub.group(1).strip() if pub else None,
            "deskripsi": re.sub(r"\s+", " ", d).strip(),
            "kategori": ", ".join(unescape(c).strip() for c in cats),
        })
    return out


def fetch_page(page: int) -> list[dict]:
    url = FEED_BASE if page == 1 else f"{FEED_BASE}?paged={page}"
    try:
        r = requests.get(url, timeout=30, headers=HEADERS)
        if r.status_code == 404:
            return []  # habis halamannya
        r.raise_for_status()
    except Exception as e:  # noqa: BLE001
        print(f"  GAGAL fetch halaman {page}: {e}")
        return []
    return parse_feed(r.text)


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--pages", type=int, default=3, help="Jumlah halaman feed diambil (10 post/halaman)")
    args = ap.parse_args()

    engine = db.get_engine()
    if not db.table_exists(engine, TABLE):
        raise SystemExit(f"Tabel {TABLE} belum ada -- jalankan dulu scripts/migrasi_tabel_berita_dcse.py")

    now = datetime.now()
    total_fetched = 0
    total_saved = 0
    total_relevan = 0
    for page in range(1, args.pages + 1):
        items = fetch_page(page)
        if not items:
            print(f"[halaman {page}] kosong/404 -- berhenti (sudah sampai akhir arsip atau gagal fetch)")
            break
        rows = []
        for it in items:
            relevan = is_relevan_mei(it["judul"], it["deskripsi"], it["kategori"])
            total_relevan += int(relevan)
            rows.append((it["url"], it["judul"], it["tanggal"], it["deskripsi"], it["kategori"],
                         int(relevan), now))
        saved = db.upsert(
            engine, TABLE, COLUMNS, rows,
            update_columns=["judul", "tanggal", "deskripsi", "kategori", "relevan_mei", "fetched_at"],
            label=f"upsert berita dcse halaman {page}",
        )
        total_fetched += len(items)
        total_saved += saved
        print(f"[halaman {page}] {len(items)} post ({saved} tersimpan/diperbarui)")
        if page < args.pages:
            time.sleep(REQUEST_DELAY_SEC)

    print(f"\nSELESAI. {total_fetched} post diambil, {total_saved} tersimpan/diperbarui, "
          f"{total_relevan} ditandai relevan_mei=1 (perlu verifikasi manual sebelum dipakai sbg bukti resmi).")
    with engine.connect() as conn:
        n_total = conn.exec_driver_sql(f"SELECT COUNT(*) FROM `{TABLE}`").scalar()
        n_relevan = conn.exec_driver_sql(f"SELECT COUNT(*) FROM `{TABLE}` WHERE relevan_mei=1").scalar()
    print(f"Total baris di tabel {TABLE} sekarang: {n_total} ({n_relevan} relevan_mei=1)")


if __name__ == "__main__":
    main()
