"""Fetch detail berita UGM dari sitemap yang relevan dampak.

Baca daftar URL dari tabel `berita_sitemap`, filter yang cocok dengan kata
kunci topik dampak (di slug URL), lalu fetch halaman untuk mengambil judul
(h1), deskripsi (meta description), tanggal terbit (datePublished), DAN isi
lengkap artikel + kredit redaksional (lewat `fetch_full()` dari
scripts/fetch_backlog.py -- SUMBER TUNGGAL logika ekstraksi isi/kredit,
JANGAN duplikat di sini, lihat docstring fetch_backlog.py).
Hasil disimpan ke tabel `berita_berita` (sumber='sitemap').
Fetch berjalan paralel (8 thread) dengan throttle ringan.

Kandidat = URL sitemap yang cocok kata kunci topik dampak DAN belum punya
`isi` terisi di berita_berita (bukan sekadar "belum ada baris sama sekali")
-- supaya artikel yang sudah masuk lewat ingest.py (RSS, sumber='rss', cuma
judul+deskripsi pendek) atau fetch pra-fitur isi/kredit ikut ke-refetch dan
otomatis dapat isi/kredit tanpa backfill manual (bug yang diperbaiki
2026-09-01, lihat PIPELINE.md) -- KECUALI yang sudah gagal >=3x berturut-turut
(kolom `fetch_gagal_count`, lihat MAX_GAGAL & bump_fail_counts() di
fetch_backlog.py) supaya URL yang memang bermasalah (timeout permanen,
halaman tanpa konten yang bisa diekstrak) tidak dicoba ulang setiap minggu
selamanya dan buang-buang request.
"""

import re
import sys
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from db import ensure_url_primary_key, get_engine, t, upsert, with_retry  # noqa: E402
from fetch_backlog import (  # noqa: E402
    MAX_GAGAL,
    bump_fail_counts,
    clean_url,
    ensure_fetch_columns,
    fetch_full,
)

# Kata kunci slug URL (ID + EN) per topik dampak — filter awal sebelum fetch.
SLUG_TOPICS = {
    "rehabilitasi_lingkungan": [
        "lingkungan", "konservasi", "rehabilitasi", "restorasi", "penghijauan",
        "mangrove", "hutan", "ekosistem", "sampah", "environment", "conservation",
        "restoration", "reforestation", "forest", "ecosystem", "waste", "green",
    ],
    "kewirausahaan": [
        "wirausaha", "umkm", "startup", "kewirausahaan", "bisnis", "usaha",
        "enterpreneur", "entrepreneur", "enterprise", "smb", "inkubasi",
    ],
    "kunjungan_akademik": [
        "kunjungan", "studi-banding", "studi banding", "delegasi", "kunker",
        "visit", "delegation", "study-tour", "benchmark", "audiensi",
    ],
    "kolaborasi_riset": [
        "riset", "penelitian", "kolaborasi", "kerja-sama", "kerjasama",
        "research", "collaboration", "cooperation", "partnership", "moa", "mou",
    ],
}


def build_slug_regex() -> str:
    kws = [w for ws in SLUG_TOPICS.values() for w in ws]
    return "|".join(re.escape(w) for w in sorted(kws, key=len, reverse=True))


BATCH_SIZE = 100
COLUMNS = ["url", "judul", "tanggal", "deskripsi", "kategori", "sumber", "isi", "kredit"]


def main() -> None:
    engine = get_engine()
    sitemap_table = t("sitemap")
    berita_table = t("berita")
    with engine.begin() as conn:
        conn.exec_driver_sql(
            f"""
            CREATE TABLE IF NOT EXISTS `{berita_table}` (
                url VARCHAR(500) PRIMARY KEY,
                judul TEXT,
                tanggal VARCHAR(40),
                deskripsi TEXT,
                kategori TEXT,
                sumber VARCHAR(20),
                isi TEXT,
                kredit TEXT,
                fetch_gagal_count INT NOT NULL DEFAULT 0
            )
            """
        )
    ensure_url_primary_key(engine, berita_table)
    ensure_fetch_columns(engine)  # no-op kalau tabel di atas baru dibuat (sudah ada kolomnya)

    pattern = build_slug_regex()

    def _read_candidates():
        with engine.connect() as conn:
            rows_ = conn.exec_driver_sql(
                f"SELECT url, lastmod FROM `{sitemap_table}` WHERE LOWER(url) REGEXP %s",
                (pattern,),
            ).fetchall()
            # URL yang SUDAH punya `isi` terisi, ATAU sudah gagal >=MAX_GAGAL
            # kali berturut-turut (lihat fetch_backlog.bump_fail_counts) --
            # dalam bentuk bersih (tanpa query string / trailing slash),
            # normalisasi.py menyimpan bentuk ini. SENGAJA "isi terisi",
            # bukan "baris ada", supaya artikel yang baru masuk lewat
            # ingest.py (RSS, cuma judul+deskripsi pendek) ikut di-refetch
            # untuk dapat isi/kredit.
            existing_ = set(
                r[0]
                for r in conn.exec_driver_sql(
                    f"SELECT DISTINCT TRIM(TRAILING '/' FROM SUBSTRING_INDEX(url, '?', 1)) "
                    f"FROM `{berita_table}` WHERE (isi IS NOT NULL AND isi != '') "
                    f"OR fetch_gagal_count >= {MAX_GAGAL}"
                ).fetchall()
            )
        return rows_, existing_

    ok, result = with_retry(_read_candidates, label="baca kandidat URL dari MySQL")
    if not ok:
        print("GAGAL membaca kandidat URL dari MySQL setelah 3 percobaan -- batal.")
        return
    rows, existing = result
    rows = [r for r in rows if r[0].split("?")[0].rstrip("/") not in existing]
    print(f"URL sitemap relevan yang BELUM punya isi di tabel berita: {len(rows)}")

    total = 0
    done = 0
    buffer: list[tuple] = []
    empty_urls: list[str] = []  # isi masih kosong sesudah fetch -- lihat bump_fail_counts

    def flush() -> None:
        nonlocal buffer
        if buffer:
            # Batch kecil (<=BATCH_SIZE baris/transaksi, retry otomatis di
            # dalam upsert()) -- kalau proses berhenti di tengah (fetch bisa
            # jalan berjam-jam), baris yang sudah di-flush tetap tersimpan.
            upsert(
                engine, berita_table, COLUMNS, buffer,
                update_columns=["judul", "tanggal", "deskripsi", "kategori", "sumber", "isi", "kredit"],
                chunk_size=BATCH_SIZE,
            )
            buffer = []

    with ThreadPoolExecutor(max_workers=8) as pool:
        futures = {pool.submit(fetch_full, url): (url, lastmod) for url, lastmod in rows}
        for fut in as_completed(futures):
            url, lastmod = futures[fut]
            detail = fut.result()
            done += 1
            if not detail:
                empty_urls.append(url)
                if done % 500 == 0:
                    print(f"  ... {done}/{len(rows)} ({total} tersimpan)")
                continue
            if not detail["isi"]:
                empty_urls.append(url)
            buffer.append((
                clean_url(url), detail["judul"], detail["tanggal"] or lastmod,
                detail["deskripsi"], "", "sitemap", detail["isi"], detail["kredit"],
            ))
            total += 1
            if len(buffer) >= BATCH_SIZE:
                flush()
            if done % 100 == 0:
                print(f"  ... {done}/{len(rows)} ({total} tersimpan)")
            time.sleep(0.05)  # throttle ringan
    flush()
    bump_fail_counts(engine, empty_urls)

    with engine.connect() as conn:
        n = conn.exec_driver_sql(f"SELECT COUNT(*) FROM `{berita_table}`").scalar()
    print(f"SELESAI. {total} detail baru tersimpan. Total baris berita: {n}")


if __name__ == "__main__":
    main()
