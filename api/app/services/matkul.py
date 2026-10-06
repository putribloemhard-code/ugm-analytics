"""Loader data mata kuliah sustainability (subproyek matkul-sustainability).

Sumber: `matkul-sustainability/data/Deskripsi Matkul Kepmen.csv` (kurasi manual, 8.465
baris penawaran MK) + `Ringkasan Indikator Kepmen.pdf` (angka resmi & catatan metode).

Struktur CSV (dipisah `;`, encoding cp1252):
    Jenjang;fakultas/sekolah;prodi;nama_mk;semester;deskripsi_mk;
    sumber_deskripsi;status_kepmen;kriteria_kepmen_match;keyword_match

Status yang dihitung ke indikator: `Substansial – dihitung` (Kepmen no. 2: MK yang
hanya menyinggung sepintas tidak dihitung). Angka resmi dari Ringkasan PDF:
511 baris penawaran = 453 MK unik (dedup nama_mk, kasus/whitespace dinormalkan).

KAITAN KE TEMA KEPMEN — penting, jangan dikaburkan:
- Indikator "Jumlah mata kuliah/modul yang memuat materi sustainability dan biodiversitas"
  adalah tema 4.5 `pendidikan_dan_penelitian` (Dampak Lingkungan). Kriteria a–j di PDF
  Ringkasan PERSIS kriteria tema itu. Jadi SEMUA MK substansial terkait tema 4.5.
- Sejak 2026-10-06 `tag_tema` HANYA memetakan MK ke tema 4.5 (indikator resmi satu-satunya).
  Perluasan ke tema lain (kriteria kurasi & leksikon kurikulum Sosial/Ekonomi) dihapus atas
  keputusan pengguna: dashboard tidak menampilkan MK di pilar Sosial/Ekonomi.

Angka resmi (511 baris / 453 MK unik / 142 parsial + jumlah per kriteria a–j) hidup di
`ringkasan_kepmen.py` — hasil konversi `Ringkasan Indikator Kepmen.md`/`.json`. Tiap kali
data dimuat, `load_matkul()` mencek-silang CSV vs angka resmi itu (`cek_silang_csv`) dan
mencatat perbedaan lewat logger — data tidak bisa diam-diam menyimpang dari Ringkasan.
"""
from __future__ import annotations

import logging
import re
from collections import Counter
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

import pandas as pd

from app.domain.source import kepmen
from app.services.ringkasan_kepmen import KRITERIA_RESMI, cek_silang_csv

logger = logging.getLogger(__name__)

REPO_ROOT = Path(__file__).resolve().parents[3]
MATKUL_CSV = REPO_ROOT / "matkul-sustainability" / "data" / "Deskripsi Matkul Kepmen.csv"

# Tema Kepmen pemilik indikator ini (kriteria a–j ada di tema ini).
TEMA_INDIKATOR = "pendidikan_dan_penelitian"

STATUS_SUBSTANSIAL = "Substansial – dihitung"
STATUS_PARSIAL = "Parsial/bergantung topik – verifikasi RPS"

# Kriteria a–j -> label tampilan (sheet "Keyword Kepmen").
KRITERIA_LABEL: dict[str, str] = {
    "a": "Pembangunan berkelanjutan",
    "b": "Perubahan iklim",
    "c": "Energi terbarukan",
    "d": "Pengelolaan limbah",
    "e": "Ekonomi sirkular",
    "f": "Konservasi lingkungan",
    "g": "Keanekaragaman hayati",
    "h": "Rehabilitasi dan restorasi lingkungan",
    "i": "Pengelolaan sumber daya alam",
    "j": "Topik lain relevan",
}


# ---- Tagging MK ke tema Kepmen: hanya indikator resmi tema 4.5 --------------------------
DASAR_RESMI = "Indikator resmi (tema 4.5)"

# Status yang tidak ikut tagging SDG: nama MK berupa kode/tak lengkap.
STATUS_TAK_DINILAI = "Belum dapat dinilai – cek kurikulum"


def _pola_sdg(kata: list[str]) -> re.Pattern[str]:
    """Konvensi tag_sdg_langsung.py: <=5 huruf -> kata utuh, lebih panjang -> substring."""
    bagian = [rf"\b{re.escape(k)}\b" if len(k) <= 5 else re.escape(k) for k in sorted(kata, key=len, reverse=True)]
    return re.compile("|".join(bagian), re.IGNORECASE)


def _unik(df: pd.DataFrame) -> pd.DataFrame:
    """Dedup nama MK (Ringkasan: 1 MK dihitung 1 kali walau ditawarkan di >1 kelas/prodi)."""
    return (df.assign(_k=df["nama_mk"].str.lower())
            .sort_values("fakultas", kind="stable")
            .drop_duplicates(subset=["_k"])
            .drop(columns=["_k"]))


def tag_tema(baris: pd.DataFrame, mk_unik: pd.DataFrame) -> pd.DataFrame:
    """Satu baris per MK unik Substansial di tema 4.5 (indikator resmi): kolom tema, dasar, pemicu
    (kriteria a-j) + identitas MK. `baris` tidak dipakai lagi; dipertahankan demi tanda tangan."""
    kolom = ["nama_mk", "fakultas", "prodi", "jenjang", "status", "kriteria", "keywords", "deskripsi"]
    return mk_unik[kolom].assign(
        tema=TEMA_INDIKATOR, dasar=DASAR_RESMI,
        pemicu=mk_unik["kriteria"].map(lambda k: ", ".join(KRITERIA_LABEL.get(h, h) for h in huruf_kriteria(k))),
    ).reset_index(drop=True)


def tag_sdg(baris: pd.DataFrame) -> pd.DataFrame:
    """Mode "SDGs saja": MK unik -> SDG langsung dengan kamus keyword yang SAMA dengan berita
    (berita-dampak/scripts/sdg_keywords.py). Satu baris per (MK unik, sdg)."""
    from app.domain.source import load_module

    kamus = load_module("sdg_keywords.py").SDG_KEYWORDS
    dinilai = _unik(baris[(baris["nama_mk"] != "") & (baris["status"] != STATUS_TAK_DINILAI)])
    teks = (dinilai["nama_mk"] + " " + dinilai["deskripsi"]).str.lower()
    potong = []
    for nomor, isi in kamus.items():
        pola = _pola_sdg(isi["keywords"] if isinstance(isi, dict) else isi)
        pemicu = teks.map(lambda t, p=pola: ", ".join(dict.fromkeys(m.group(0).lower() for m in p.finditer(t))))
        cocok = dinilai[pemicu != ""]
        potong.append(cocok[["nama_mk", "fakultas", "prodi", "jenjang", "status", "deskripsi"]]
                      .assign(sdg=int(nomor), pemicu=pemicu[pemicu != ""]))
    return pd.concat(potong, ignore_index=True)


@dataclass
class MatkulFrames:
    """Frame mata kuliah siap analisis (paralel dengan StoryFrames)."""

    baris: pd.DataFrame  # semua baris penawaran
    substansial: pd.DataFrame  # baris berstatus Substansial
    mk_unik: pd.DataFrame  # satu baris per nama MK substansial
    sumber: str = ""
    total_penawaran: int = 0
    n_substansial: int = 0
    n_mk_unik: int = 0
    parsial: int = 0
    # Jumlah MK unik per kriteria a-j menurut Ringkasan resmi (rujukan, bukan hasil hitung).
    kriteria_resmi: dict[str, int] = field(default_factory=dict)
    # Tagging 14 tema (tag_tema) & SDG langsung (tag_sdg) -- dihitung sekali saat load.
    mk_tema: pd.DataFrame = field(default_factory=pd.DataFrame)
    mk_sdg: pd.DataFrame = field(default_factory=pd.DataFrame)


def _baca_csv() -> pd.DataFrame:
    """Baca CSV kurasi; gagal JELAS kalau tidak ada (jangan diam-diam mengosongkan dashboard)."""
    if not MATKUL_CSV.exists():
        raise FileNotFoundError(
            f"Data mata kuliah tidak ditemukan: {MATKUL_CSV}. "
            "File kurasi 'Deskripsi Matkul Kepmen.csv' harus ada di repo."
        )
    df = pd.read_csv(MATKUL_CSV, sep=";", encoding="cp1252", dtype=str).fillna("")
    df.columns = [c.strip() for c in df.columns]
    return df


def load_matkul() -> MatkulFrames:
    """Muat + hitung frame mata kuliah (dipanggil sekali, lalu di-cache StoryService).

    Sekaligus cek-silang CSV vs angka resmi Ringkasan (`cek_silang_csv`) — perbedaan
    dicatat sebagai warning (bukan exception) supaya dashboard tetap hidup, tapi
    penyimpangan data tidak bisa lolos tanpa jejak di log.
    """
    df = _baca_csv().rename(columns={
        "Jenjang": "jenjang", "fakultas/sekolah": "fakultas", "prodi": "prodi",
        "nama_mk": "nama_mk", "semester": "semester", "deskripsi_mk": "deskripsi",
        "status_kepmen": "status", "kriteria_kepmen_match": "kriteria",
        "keyword_match": "keywords",
    })
    for col in df.columns:
        df[col] = df[col].str.strip()

    substansial = df[df["status"] == STATUS_SUBSTANSIAL].copy()
    # Ringkasan PDF: satu MK dihitung 1 kali walau ditawarkan di >1 kelas/prodi.
    # Nama sama di prodi berbeda bisa MK berbeda (perlu kode MK/RPS) — dicatat di catatan UI.
    mk_unik = (
        substansial.assign(_k=substansial["nama_mk"].str.lower())
        .sort_values("fakultas", kind="stable")
        .drop_duplicates(subset=["_k"])
        .drop(columns=["_k"])
        .reset_index(drop=True)
    )
    parsial = int((df["status"] == STATUS_PARSIAL).sum())

    # Cek silang CSV vs angka resmi Ringkasan (MD/JSON). Warning, bukan exception:
    # dashboard tetap hidup, tapi penyimpangan data selalu berjejak di log.
    hitung_kriteria: Counter = Counter()
    for k in mk_unik["kriteria"]:
        hitung_kriteria.update(h.strip().lower() for h in str(k).split(",") if h.strip())
    selisih = cek_silang_csv(int(len(df)), int(len(substansial)), int(len(mk_unik)),
                             parsial, dict(hitung_kriteria))
    if not selisih.ok:
        logger.warning(
            "Angka CSV kurasi berbeda dari Ringkasan Indikator Kepmen: %s",
            "; ".join(selisih.perbedaan),
        )

    return MatkulFrames(
        baris=df, substansial=substansial, mk_unik=mk_unik,
        sumber="Deskripsi Matkul Kepmen.csv (kurasi manual)",
        total_penawaran=int(len(df)),
        n_substansial=int(len(substansial)),
        n_mk_unik=int(len(mk_unik)),
        parsial=parsial,
        kriteria_resmi=dict(KRITERIA_RESMI),
        mk_tema=tag_tema(df, mk_unik),
        mk_sdg=tag_sdg(df),
    )


def huruf_kriteria(kriteria: str) -> list[str]:
    """'a, b, i' -> ['a', 'b', 'i'] (huruf kecil, unik, urut abjad)."""
    hasil = {h.strip().lower() for h in str(kriteria).split(",") if h.strip()}
    return sorted(hasil)


def meta_tema() -> dict[str, dict[str, Any]]:
    """Metadata 14 tema dari kepmen_sdg.py — satu sumber kebenaran (dampak/topik_kepmen/sdg)."""
    mapping = kepmen()
    return {
        tema_id: {
            "dampak": meta["dampak"],
            "topik_kepmen": meta["topik_kepmen"],
            "sdg": list(meta["sdg"]),
        }
        for tema_id, meta in mapping.TOPIK_KEPMEN_ALL.items()
    }
