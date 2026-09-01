"""Tagging berita ke 44 fakultas/sekolah/unit kerja resmi UGM yang disebut
dalam judul + deskripsi (lihat scripts/unit_kerja.py untuk daftar lengkap).

Lapisan tagging INDEPENDEN dari tag_kepmen_all.py (tema Kepmen/SDG) --
tidak mengubah/menyentuh tabel atau logika tagging Kepmen sama sekali, cuma
berjalan berdampingan memakai data berita yang sama.

Konvensi matching (mengikuti pola tag_kepmen_all.py, lihat docs/FRAMEWORK.md
bagian "Konvensi tagging"): substring case-insensitive pada judul + deskripsi
+ isi lengkap artikel kalau kolom `isi` sudah ada (scripts/fetch_backlog.py;
fallback ke judul+deskripsi saja kalau backlog itu belum pernah dijalankan).
Kolom `kredit` (baris kredit redaksional yang dipisahkan dari `isi`) SENGAJA
TIDAK diikutkan dalam matching -- unit yang cuma menerbitkan berita (mis.
"/Humas FEB" di baris kredit) belum tentu unit yang benar-benar dibahas.
Keyword per unit = NAMA RESMI PENUH saja (mis. "Fakultas Hukum", bukan cuma
"hukum") -- sengaja TIDAK memakai singkatan (FEB/FT/FH/FISIPOL/dst) karena
singkatan pendek berisiko tinggi salah cocok dengan kata/akronim lain di luar
konteks UGM; keputusan menambah singkatan MENUNGGU validasi eksplisit
terpisah (lihat laporan validasi -- false-positive-prone units perlu
keputusan pemilik project sebelum singkatan ditambahkan).

Guard leakage lintas-universitas: nama fakultas/unit yang generik (mis.
"Fakultas Pertanian") kadang jadi milik universitas LAIN yang disebut dalam
berita yang sama (mis. "Dosen Fakultas Pertanian Universitas Negeri
Gorontalo"). Kalau satu occurrence nama unit langsung diikuti frasa
"Universitas <nama>" dengan <nama> BUKAN "Gadjah Mada", occurrence itu
di-skip (bukan bukti unit UGM ini disebut) -- lihat `_match_valid()`. Berita
tetap match kalau ADA occurrence lain dari nama unit yang sama tanpa
"Universitas <nama lain>" mengikutinya (mis. "...Fakultas Pertanian UGM..."
di kalimat lain pada berita yang sama).

Berita bisa kena banyak unit sekaligus (multi-tag by design, sama seperti
tagging tema Kepmen).

Output tabel baru (idempoten, DROP + recreate -- tabel derivatif dihitung
ulang penuh tiap run dari teks berita, sama seperti berita_kepmen_all,
BUKAN tabel akumulatif per-item sehingga tidak pakai db.upsert(); lihat
"Koneksi MySQL -- aturan penting" di FRAMEWORK.md):
  - berita_unit_kerja : url, unit_kerja, kategori

Jalankan (dari folder berita-dampak):
  ../venv/Scripts/python.exe scripts/tag_unit_kerja.py
"""

import re
import sys
from pathlib import Path

import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parent))
from db import column_exists, get_engine, read_sql_retry, t, with_retry  # noqa: E402
from unit_kerja import UNIT_KERJA  # noqa: E402

# Toleransi kecil spasi/tanda baca antara nama unit dan "Universitas <nama>"
# yang mengikutinya langsung sesudahnya (koma, tanda hubung, kurung).
_GAP = r"[\s,\-–—()]{0,4}"
_UNIV_LAIN_RE = re.compile(rf"^{_GAP}universitas\s+([a-z]+)")


def _match_valid(teks: str, pattern: str) -> bool:
    """True kalau ADA >=1 occurrence keyword unit di teks yang TIDAK langsung
    diikuti "Universitas <nama lain>" (leakage lintas-universitas -- lihat
    docstring modul). Occurrence yang diikuti "Universitas Gadjah Mada", atau
    tidak diikuti "Universitas ..." sama sekali, dianggap valid seperti biasa.
    """
    for m in re.finditer(pattern, teks):
        ekor = teks[m.end():m.end() + 60]
        um = _UNIV_LAIN_RE.match(ekor)
        if um and um.group(1) != "gadjah":
            continue
        return True
    return False


def main() -> None:
    engine = get_engine()
    # isi lengkap (scripts/fetch_backlog.py) baru ada setelah backlog itu
    # pernah dijalankan -- cek dulu, fallback ke judul+deskripsi kalau belum.
    # `kredit` SENGAJA tidak diikutkan -- baris kredit redaksional (mis.
    # "/Humas FEB") bisa salah men-tag unit yang cuma menerbitkan berita,
    # bukan yang benar-benar dibahas artikelnya (lihat docstring modul).
    has_isi = column_exists(engine, t("berita"), "isi")
    kolom = "url, judul, deskripsi" + (", isi" if has_isi else "")
    berita = read_sql_retry(engine, f"SELECT {kolom} FROM `{t('berita')}`",
                             label="baca berita")

    rows = []
    for _, r in berita.iterrows():
        teks = f"{r['judul'] or ''} {r['deskripsi'] or ''}"
        if has_isi:
            teks += f" {r['isi'] or ''}"
        teks = teks.lower()
        for unit_id, m in UNIT_KERJA.items():
            kw = m["nama"].lower()
            # Sama seperti tag_kepmen_all.py: keyword <=5 huruf pakai batas
            # kata (\b...\b) -- tidak ada nama unit sependek itu, tapi aturan
            # dipertahankan untuk konsistensi kalau suatu saat ada tambahan.
            pattern = rf"\b{re.escape(kw)}\b" if len(kw) <= 5 else re.escape(kw)
            if _match_valid(teks, pattern):
                rows.append({"url": r["url"], "unit_kerja": unit_id, "kategori": m["kategori"]})

    df = pd.DataFrame(rows, columns=["url", "unit_kerja", "kategori"])

    ok, _ = with_retry(
        lambda: df.to_sql(t("unit_kerja"), engine, if_exists="replace", index=False),
        label="tulis berita_unit_kerja",
    )

    n_berita = df["url"].nunique() if len(df) else 0
    print(f"Baris url-unit: {len(df)}")
    print(f"Berita unik yang match >=1 unit: {n_berita} / {len(berita)} "
          f"({100 * n_berita / len(berita):.1f}%)" if len(berita) else "")
    if not ok:
        print("PERINGATAN: tabel berita_unit_kerja gagal ditulis setelah retry.")
    else:
        print("Tabel: berita_unit_kerja")


if __name__ == "__main__":
    main()
