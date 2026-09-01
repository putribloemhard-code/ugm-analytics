"""Tagging topik dampak pada berita UGM (substring match pada judul +
deskripsi + isi lengkap artikel kalau sudah ada -- lihat scripts/fetch_backlog.py).

Menggunakan kamus keywords.py. Satu berita bisa masuk lebih dari satu topik.
Hasil: tabel `berita_topik` (url, topik) dan tabel `ringkasan_topik_tahun`.
"""

import re
import sys
from pathlib import Path

import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parent))
from db import column_exists, get_engine, read_sql_retry, t, with_retry  # noqa: E402
from keywords import KEYWORDS  # noqa: E402


def tag(text: str) -> list[str]:
    t = text.lower()
    hits = []
    for topik, kws in KEYWORDS.items():
        for kw in kws:
            if kw in t:
                hits.append(topik)
                break
    return hits


def main() -> None:
    engine = get_engine()
    # isi lengkap (kolom `isi`, dari scripts/fetch_backlog.py) baru ada
    # setelah backlog itu pernah dijalankan -- cek dulu, jangan asumsikan
    # ada, biar script ini tetap jalan di DB sebelum/sesudahnya.
    has_isi = column_exists(engine, t("berita"), "isi")
    kolom = "url, judul, deskripsi, tanggal" + (", isi" if has_isi else "")
    berita = read_sql_retry(engine, f"SELECT {kolom} FROM `{t('berita')}`",
                             label="baca berita")

    def teks_berita(r) -> str:
        dasar = f"{r['judul']} {r['deskripsi']}"
        return f"{dasar} {r['isi'] or ''}" if has_isi else dasar

    tagged = [
        (r["url"], topik)
        for _, r in berita.iterrows()
        for topik in tag(teks_berita(r))
    ]
    df_topik = pd.DataFrame(tagged, columns=["url", "topik"])

    df_ring = (
        df_topik.merge(berita[["url", "tanggal"]], on="url", how="left")
        .dropna(subset=["tanggal"])
    )
    df_ring["tahun"] = df_ring["tanggal"].str[:4]
    ringkasan = (
        df_ring.groupby(["topik", "tahun"])
        .size()
        .reset_index(name="jumlah")
        .sort_values(["topik", "tahun"])
    )

    ok1, _ = with_retry(
        lambda: df_topik.to_sql(t("berita_topik"), engine, if_exists="replace", index=False),
        label="tulis berita_topik",
    )
    ok2, _ = with_retry(
        lambda: ringkasan.to_sql(t("ringkasan_topik_tahun"), engine, if_exists="replace", index=False),
        label="tulis ringkasan_topik_tahun",
    )
    if not (ok1 and ok2):
        print("PERINGATAN: sebagian tabel gagal ditulis ke MySQL setelah retry -- cek log di atas.")

    print("Per topik:")
    for topik, n in df_topik.groupby("topik").size().sort_values(ascending=False).items():
        print(f"  {topik}: {n} berita")
    print(f"Total pasangan topik: {len(tagged)}")


if __name__ == "__main__":
    main()
