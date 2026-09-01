"""Fetch ISI LENGKAP tiap artikel berita UGM (bukan cuma judul + deskripsi
pendek dari meta tag seperti fetch_detail.py) untuk URL di `berita_sitemap`
yang kolom `isi`-nya masih NULL/kosong di `berita_berita` -- termasuk yang
sudah pernah di-fetch judul/deskripsinya oleh fetch_detail.py (di-fetch ulang
sekali lagi, judul/deskripsi/tanggal ikut diperbarui dari fetch yang sama,
tidak fetch dua kali per URL).

Selector isi artikel (TERVALIDASI manual pada 17 sampel lintas tahun
2008-2026, kedua pola URL /id/berita/ dan /en/news/ -- lihat percakapan
validasi Fase 1 sebelum script ini dibuat): `div.inner-content` (nested di
`div.post-content` > `article.single-post`). Konsisten di semua sampel;
tidak ada boilerplate ("Baca juga", tombol share, related post, komentar)
yang ikut ter-scrape -- elemen itu hidup di sibling `div.share-box-wrap` di
LUAR `div.inner-content`, otomatis ter-exclude karena kita scope langsung ke
situ.

Baris kredit redaksional (mis. "Penulis: Ika", "Reportase : X/Humas FEB",
"Author: X | Editor: Y | Post-editor: Z | Illustration: W") dipisahkan dari
isi ke kolom `kredit` -- lihat `_split_kredit()`. Kalau paragraf(-paragraf)
trailing tidak jelas match pola "Label: nilai" pendek, SEMUA teks tetap
masuk `isi` apa adanya (safe default -- validasi Fase 1 mengonfirmasi gaya
lama seperti "...ujarnya. (Humas UGM/Nama)" yang menyatu di kalimat
terakhir TIDAK coba dipisah, karena bukan paragraf tersendiri).

Kolom baru di `berita_berita` (ditambah otomatis sekali kalau belum ada):
  - isi     TEXT       -- isi artikel bersih, TANPA baris kredit
  - kredit  TEXT NULL  -- baris kredit yang terdeteksi & dipisahkan

WAJIB baca juga: scripts/normalisasi.py sudah diupdate untuk ikut membawa
isi/kredit saat DELETE+INSERT ulang tabel berita -- JANGAN jalankan versi
lama normalisasi.py setelah backlog ini terisi, nanti isi/kredit hilang.

Konvensi mengikuti fetch_detail.py: requests + ThreadPoolExecutor (8
thread), throttle ringan, upsert per batch (idempoten, resumable). Lock
file `data/.fetch_backlog_lock` mencegah run ganda; juga cek lock
`data/.update_lock` punya update_mingguan.py supaya tidak bentrok fetch
bersamaan. Progress + estimasi sisa waktu di-log ke
`logs_fetch_backlog.txt` (bukan cuma konsol -- supaya bisa dipantau kalau
dijalankan di background).

Jalankan (dari folder berita-dampak):
  ../venv/Scripts/python.exe scripts/fetch_backlog.py                 # semua URL isi masih kosong (32.130)
  ../venv/Scripts/python.exe scripts/fetch_backlog.py --limit 20      # sampel kecil (validasi manual dulu)
  ../venv/Scripts/python.exe scripts/fetch_backlog.py --urls-file f.txt  # daftar URL spesifik (satu per baris)
"""

import argparse
import os
import re
import sys
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path

import requests
from bs4 import BeautifulSoup

sys.path.insert(0, str(Path(__file__).resolve().parent))
from db import ensure_url_primary_key, get_engine, t, upsert, with_retry  # noqa: E402

ROOT = Path(__file__).resolve().parents[1]
LOCK = ROOT / "data" / ".fetch_backlog_lock"
UPDATE_LOCK = ROOT / "data" / ".update_lock"
LOG_FILE = ROOT / "logs_fetch_backlog.txt"

HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/126.0 Safari/537.36",
    "Accept-Language": "id-ID,id;q=0.9,en;q=0.8",
}

BOILERPLATE_HINTS = re.compile(
    r"baca juga|artikel terkait|related post|share this|tinggalkan komentar|"
    r"leave a comment|read also|see also|^tags?:",
    re.I,
)
CREDIT_LABEL_RE = re.compile(
    r"^(penulis|reportase|author|editor|post-editor|posted by|foto|photo|"
    r"fotografer|dokumentasi|kontributor|sumber foto|translator|penerjemah|"
    r"ilustrasi|illustration|editor bahasa|photographer|redaktur)\s*:\s*.+$",
    re.IGNORECASE,
)
CREDIT_MAX_LEN = 150

BATCH_SIZE = 500
COLUMNS = ["url", "judul", "tanggal", "deskripsi", "kategori", "sumber", "isi", "kredit"]


def _log(msg: str) -> None:
    line = f"{time.strftime('%Y-%m-%d %H:%M:%S')} {msg}"
    print(line, flush=True)
    with open(LOG_FILE, "a", encoding="utf-8") as f:
        f.write(line + "\n")


def clean_url(u: str) -> str:
    return u.strip().split("?")[0].rstrip("/")


def _extract_isi_kredit(soup: BeautifulSoup) -> tuple[str, str | None]:
    """Ambil isi artikel bersih + kredit terpisah dari div.inner-content
    (lihat validasi selector di docstring modul)."""
    container = soup.find("div", class_="inner-content")
    if container is None:
        return "", None
    parts = []
    for p in container.find_all(["p", "li"]):
        txt = p.get_text(" ", strip=True)
        if not txt or BOILERPLATE_HINTS.search(txt):
            continue
        parts.append(re.sub(r"[ \t]+", " ", txt))
    if not parts:
        return "", None
    kredit_parts: list[str] = []
    while parts and CREDIT_LABEL_RE.match(parts[-1]) and len(parts[-1]) <= CREDIT_MAX_LEN:
        kredit_parts.insert(0, parts.pop())
    isi = "\n\n".join(parts).strip()
    kredit = " | ".join(kredit_parts) if kredit_parts else None
    return isi, kredit


def fetch_full(url: str, retries: int = 3) -> dict | None:
    """Fetch SATU KALI, ambil judul/tanggal/deskripsi (sama seperti
    fetch_detail.py) SEKALIGUS isi/kredit dari HTML yang sama -- tidak fetch
    ulang halaman yang sama dua kali."""
    for attempt in range(retries):
        try:
            r = requests.get(url, timeout=45, headers=HEADERS)
            if r.status_code != 200:
                return None
            teks = r.text
            h1 = re.findall(r"<h1[^>]*>(.*?)</h1>", teks, re.S)
            desc = re.search(r'<meta name="description" content="(.*?)"', teks, re.S)
            date = re.search(r'"datePublished"\s*:\s*"([^"]+)"', teks)
            judul = re.sub(r"\s+", " ", re.sub(r"<[^>]+>", "", h1[0])).strip() if h1 else ""
            if not judul:
                og = re.search(r'property="og:title" content="(.*?)"', teks, re.S)
                if og:
                    judul = og.group(1).split(" - ")[0].strip()
            if desc:
                deskripsi = re.sub(r"\s+", " ", desc.group(1)).strip()
            else:
                ogd = re.search(r'property="og:description" content="(.*?)"', teks, re.S)
                deskripsi = re.sub(r"\s+", " ", ogd.group(1)).strip() if ogd else ""

            soup = BeautifulSoup(teks, "html.parser")
            isi, kredit = _extract_isi_kredit(soup)

            return {
                "judul": judul,
                "tanggal": date.group(1) if date else None,
                "deskripsi": deskripsi,
                "isi": isi,
                "kredit": kredit,
            }
        except Exception:  # noqa: BLE001
            time.sleep(2 * (attempt + 1))
    return None


def _ensure_columns(engine) -> None:
    def _check_and_add() -> None:
        with engine.begin() as conn:
            existing = {
                row[0] for row in conn.exec_driver_sql(
                    f"SHOW COLUMNS FROM `{t('berita')}`"
                ).fetchall()
            }
            if "isi" not in existing:
                conn.exec_driver_sql(f"ALTER TABLE `{t('berita')}` ADD COLUMN `isi` TEXT")
            if "kredit" not in existing:
                conn.exec_driver_sql(f"ALTER TABLE `{t('berita')}` ADD COLUMN `kredit` TEXT")

    ok, _ = with_retry(_check_and_add, label="pastikan kolom isi/kredit ada")
    if not ok:
        raise RuntimeError("Gagal memastikan kolom isi/kredit ada di berita_berita.")


def _read_candidates(engine, limit: int | None) -> list[tuple[str, str]]:
    """URL sitemap yang kolom isi-nya di berita_berita masih NULL/kosong,
    ATAU belum ada baris berita sama sekali untuk URL itu."""
    def _query():
        with engine.connect() as conn:
            sql = f"""
                SELECT sm.url, sm.lastmod
                FROM `{t('sitemap')}` sm
                LEFT JOIN `{t('berita')}` b
                  ON TRIM(TRAILING '/' FROM SUBSTRING_INDEX(sm.url, '?', 1)) = b.url
                WHERE b.url IS NULL OR b.isi IS NULL OR b.isi = ''
            """
            return conn.exec_driver_sql(sql).fetchall()

    ok, rows = with_retry(_query, label="baca kandidat URL backlog dari MySQL")
    if not ok:
        raise RuntimeError("Gagal membaca kandidat URL dari MySQL setelah 3 percobaan.")
    rows = [(r[0], r[1]) for r in rows]
    if limit:
        rows = rows[:limit]
    return rows


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--limit", type=int, default=None,
                     help="Batasi jumlah URL yang diproses (untuk sampel/uji kecil).")
    ap.add_argument("--urls-file", type=str, default=None,
                     help="Path file teks berisi daftar URL spesifik (satu per baris), "
                          "override seleksi kandidat otomatis.")
    args = ap.parse_args()

    if LOCK.exists():
        pid = LOCK.read_text().strip()
        _log(f"DIBATALKAN -- fetch_backlog lain sedang berjalan (PID {pid}).")
        sys.exit(2)
    if UPDATE_LOCK.exists():
        pid = UPDATE_LOCK.read_text().strip()
        _log(f"DIBATALKAN -- update_mingguan.py sedang berjalan (PID {pid}), coba lagi nanti.")
        sys.exit(2)

    LOCK.write_text(str(os.getpid()))
    try:
        engine = get_engine()
        ensure_url_primary_key(engine, t("berita"))
        _ensure_columns(engine)

        if args.urls_file:
            urls = [
                ln.strip() for ln in Path(args.urls_file).read_text(encoding="utf-8").splitlines()
                if ln.strip()
            ]
            rows = [(u, None) for u in urls]
        else:
            rows = _read_candidates(engine, args.limit)

        total = len(rows)
        _log(f"=== FETCH BACKLOG mulai (PID {os.getpid()}) -- {total} URL kandidat ===")
        if not total:
            _log("Tidak ada URL kandidat (semua sudah punya isi). Selesai.")
            return

        done = 0
        ok_count = 0
        fail_count = 0
        buffer: list[tuple] = []
        t0 = time.time()

        def flush() -> None:
            nonlocal buffer
            if buffer:
                upsert(
                    engine, t("berita"), COLUMNS, buffer,
                    update_columns=["judul", "tanggal", "deskripsi", "kategori", "sumber", "isi", "kredit"],
                    chunk_size=BATCH_SIZE,
                    label="upsert berita (fetch_backlog)",
                )
                buffer = []

        with ThreadPoolExecutor(max_workers=8) as pool:
            futures = {pool.submit(fetch_full, url): (url, lastmod) for url, lastmod in rows}
            for fut in as_completed(futures):
                url, lastmod = futures[fut]
                detail = fut.result()
                done += 1
                if not detail:
                    fail_count += 1
                else:
                    ok_count += 1
                    buffer.append((
                        clean_url(url), detail["judul"], detail["tanggal"] or lastmod,
                        detail["deskripsi"], "", "sitemap", detail["isi"], detail["kredit"],
                    ))
                    if len(buffer) >= BATCH_SIZE:
                        flush()
                        _log(f"  ... commit batch -- {done}/{total} diproses "
                             f"({ok_count} ok, {fail_count} gagal)")
                if done % 500 == 0 or done == total:
                    elapsed = time.time() - t0
                    rate = done / elapsed if elapsed > 0 else 0
                    sisa = (total - done) / rate if rate > 0 else float("nan")
                    _log(f"  ... {done}/{total} ({ok_count} ok, {fail_count} gagal) "
                         f"-- estimasi sisa waktu: {sisa/60:.1f} menit")
                time.sleep(0.05)  # throttle ringan, sama seperti fetch_detail.py
        flush()

        with engine.connect() as conn:
            n_isi = conn.exec_driver_sql(
                f"SELECT COUNT(*) FROM `{t('berita')}` WHERE isi IS NOT NULL AND isi != ''"
            ).scalar()
        _log(f"=== SELESAI. {ok_count} berhasil, {fail_count} gagal dari {total} URL. "
             f"Total baris dengan isi terisi: {n_isi}. Waktu: {(time.time()-t0)/60:.1f} menit ===")
    finally:
        try:
            LOCK.unlink()
        except OSError:
            pass


if __name__ == "__main__":
    main()
