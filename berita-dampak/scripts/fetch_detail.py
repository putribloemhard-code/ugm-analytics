"""Fetch detail berita UGM dari sitemap yang relevan dampak.

Baca daftar URL dari tabel `berita_sitemap`, filter yang cocok dengan kata
kunci topik dampak (di slug URL), lalu fetch halaman untuk mengambil judul
(h1), deskripsi (meta description), dan tanggal terbit (datePublished).
Hasil disimpan ke tabel `berita_berita` (sumber='sitemap').
Fetch berjalan paralel (8 thread) dengan throttle ringan.
"""

import re
import sys
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path

import requests

sys.path.insert(0, str(Path(__file__).resolve().parent))
from db import ensure_url_primary_key, get_engine, t, upsert, with_retry  # noqa: E402

HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/126.0 Safari/537.36",
    "Accept-Language": "id-ID,id;q=0.9,en;q=0.8",
}

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


def fetch_detail(url: str, retries: int = 3) -> dict | None:
    for attempt in range(retries):
        try:
            r = requests.get(url, timeout=45, headers=HEADERS)
            if r.status_code != 200:
                return None
            t = r.text
            h1 = re.findall(r"<h1[^>]*>(.*?)</h1>", t, re.S)
            desc = re.search(r'<meta name="description" content="(.*?)"', t, re.S)
            date = re.search(r'"datePublished"\s*:\s*"([^"]+)"', t)
            judul = re.sub(r"\s+", " ", re.sub(r"<[^>]+>", "", h1[0])).strip() if h1 else ""
            if not judul:
                og = re.search(r'property="og:title" content="(.*?)"', t, re.S)
                if og:
                    judul = og.group(1).split(" - ")[0].strip()
            if desc:
                deskripsi = re.sub(r"\s+", " ", desc.group(1)).strip()
            else:
                # Banyak halaman tidak punya meta name=description tapi punya
                # og:description — pakai itu sebagai fallback (2026-08-20).
                ogd = re.search(r'property="og:description" content="(.*?)"', t, re.S)
                deskripsi = re.sub(r"\s+", " ", ogd.group(1)).strip() if ogd else ""
            return {
                "judul": judul,
                "tanggal": date.group(1) if date else None,
                "deskripsi": deskripsi,
            }
        except Exception:  # noqa: BLE001
            time.sleep(2 * (attempt + 1))
    return None


BATCH_SIZE = 100
COLUMNS = ["url", "judul", "tanggal", "deskripsi", "kategori", "sumber"]


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
                sumber VARCHAR(20)
            )
            """
        )
    ensure_url_primary_key(engine, berita_table)

    pattern = build_slug_regex()

    def _read_candidates():
        with engine.connect() as conn:
            rows_ = conn.exec_driver_sql(
                f"SELECT url, lastmod FROM `{sitemap_table}` WHERE LOWER(url) REGEXP %s",
                (pattern,),
            ).fetchall()
            # URL yang SUDAH ADA di tabel berita, dalam bentuk bersih (tanpa
            # query string / trailing slash) — normalisasi.py menyimpan
            # bentuk ini.
            existing_ = set(
                r[0]
                for r in conn.exec_driver_sql(
                    f"SELECT DISTINCT TRIM(TRAILING '/' FROM SUBSTRING_INDEX(url, '?', 1)) "
                    f"FROM `{berita_table}`"
                ).fetchall()
            )
        return rows_, existing_

    ok, result = with_retry(_read_candidates, label="baca kandidat URL dari MySQL")
    if not ok:
        print("GAGAL membaca kandidat URL dari MySQL setelah 3 percobaan -- batal.")
        return
    rows, existing = result
    rows = [r for r in rows if r[0].split("?")[0].rstrip("/") not in existing]
    print(f"URL sitemap relevan yang BELUM ada di tabel berita: {len(rows)}")

    total = 0
    done = 0
    buffer: list[tuple] = []

    def flush() -> None:
        nonlocal buffer
        if buffer:
            # Batch kecil (<=BATCH_SIZE baris/transaksi, retry otomatis di
            # dalam upsert()) -- kalau proses berhenti di tengah (fetch bisa
            # jalan berjam-jam), baris yang sudah di-flush tetap tersimpan.
            upsert(
                engine, berita_table, COLUMNS, buffer,
                update_columns=["judul", "tanggal", "deskripsi", "kategori", "sumber"],
                chunk_size=BATCH_SIZE,
            )
            buffer = []

    with ThreadPoolExecutor(max_workers=8) as pool:
        futures = {pool.submit(fetch_detail, url): (url, lastmod) for url, lastmod in rows}
        for fut in as_completed(futures):
            url, lastmod = futures[fut]
            detail = fut.result()
            done += 1
            if not detail:
                if done % 500 == 0:
                    print(f"  ... {done}/{len(rows)} ({total} tersimpan)")
                continue
            buffer.append((url, detail["judul"], detail["tanggal"] or lastmod, detail["deskripsi"], "", "sitemap"))
            total += 1
            if len(buffer) >= BATCH_SIZE:
                flush()
            if done % 100 == 0:
                print(f"  ... {done}/{len(rows)} ({total} tersimpan)")
            time.sleep(0.05)  # throttle ringan
    flush()

    with engine.connect() as conn:
        n = conn.exec_driver_sql(f"SELECT COUNT(*) FROM `{berita_table}`").scalar()
    print(f"SELESAI. {total} detail baru tersimpan. Total baris berita: {n}")


if __name__ == "__main__":
    main()
