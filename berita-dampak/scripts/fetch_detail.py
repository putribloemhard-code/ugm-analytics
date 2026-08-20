"""Fetch detail berita UGM dari sitemap yang relevan dampak.

Baca daftar URL dari tabel `sitemap`, filter yang cocok dengan kata kunci
topik dampak (di slug URL), lalu fetch halaman untuk mengambil judul (h1),
deskripsi (meta description), dan tanggal terbit (datePublished).
Hasil disimpan ke tabel `berita` (sumber='sitemap').
Fetch berjalan paralel (8 thread) dengan throttle ringan.
"""

import re
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path

import duckdb
import requests

DB_PATH = Path(__file__).resolve().parents[1] / "data" / "ugm_news.duckdb"
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
            deskripsi = re.sub(r"\s+", " ", desc.group(1)).strip() if desc else ""
            return {
                "judul": judul,
                "tanggal": date.group(1) if date else None,
                "deskripsi": deskripsi,
            }
        except Exception:  # noqa: BLE001
            time.sleep(2 * (attempt + 1))
    return None


def main() -> None:
    con = duckdb.connect(str(DB_PATH))
    con.execute(
        """
        CREATE TABLE IF NOT EXISTS berita (
            url VARCHAR PRIMARY KEY,
            judul VARCHAR,
            tanggal VARCHAR,
            deskripsi VARCHAR,
            kategori VARCHAR,
            sumber VARCHAR
        )
        """
    )
    pattern = build_slug_regex()
    rows = con.execute(
        f"SELECT url, lastmod FROM sitemap WHERE regexp_matches(lower(url), '{pattern}')"
    ).fetchall()
    # URL yang SUDAH ADA di tabel berita, dalam bentuk bersih (tanpa query
    # string / trailing slash) — normalisasi.py menyimpan bentuk ini.
    existing = set(
        r[0]
        for r in con.execute(
            "SELECT DISTINCT rtrim(split_part(url, '?', 1), '/') FROM berita"
        ).fetchall()
    )
    rows = [r for r in rows if r[0].split("?")[0].rstrip("/") not in existing]
    print(f"URL sitemap relevan yang BELUM ada di tabel berita: {len(rows)}")

    total = 0
    done = 0
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
            con.execute(
                "INSERT OR IGNORE INTO berita (url, judul, tanggal, deskripsi, kategori, sumber) VALUES (?,?,?,?,?,?)",
                (url, detail["judul"], detail["tanggal"] or lastmod, detail["deskripsi"], "", "sitemap"),
            )
            total += 1
            if done % 100 == 0:
                print(f"  ... {done}/{len(rows)} ({total} tersimpan)")
            time.sleep(0.05)  # throttle ringan

    n = con.execute("SELECT COUNT(*) FROM berita").fetchone()[0]
    print(f"SELESAI. {total} detail baru tersimpan. Total baris berita: {n}")
    con.close()


if __name__ == "__main__":
    main()
