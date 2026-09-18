"""Pencarian kata kunci untuk kotak "Mau analisis apa?" di Beranda.

BUKAN AI: query user dicocokkan ke kamus kata kunci yang SUDAH dipakai
pipeline tagging (scripts/keywords.KEYWORDS + TEMA_KEPMEN_LENGKAP untuk 14
tema Kepmen, LABEL_TOPIC untuk nama resmi tema) -- pendekatan yang sama
dengan tag_kepmen/tag_sdg, jadi tidak ada kamus kedua yang bisa diam-diam
beda dari kamus yang dipakai saat menandai berita.

Alur: Beranda memanggil parse() -> simpan_hasil() (tulis ke session_state)
-> st.switch_page(). Halaman tujuan memanggil terapkan_filter_awal() SEBELUM
widget filter dibuat (nilai AWAL widget, bukan filter permanen -- user tetap
bebas mengubahnya di sidebar) dan banner() untuk menjelaskan interpretasinya.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field

import streamlit as st

from common import KEYWORDS_ALL, LABEL_TOPIC
from scripts.kepmen_sdg import TOPIK_KEPMEN_ALL

# Halaman tujuan -> path file halaman (dipakai st.switch_page di Beranda).
HALAMAN = {
    "dampak": "pages_app/dampak_saja.py",
    "dampak-sdgs": "pages_app/dampak_sdgs.py",
    "sdgs": "pages_app/sdgs.py",
    "akreditasi": "pages_app/akreditasi.py",
}
NAMA_HALAMAN = {
    "dampak": "Analisis Dampak Universitas",
    "dampak-sdgs": "Dampak × SDGs",
    "sdgs": "SDGs",
    "akreditasi": "Akreditasi",
}

PILAR = ["Lingkungan", "Ekonomi", "Sosial"]
# "sdg 4", "sdgs 4", "sdg-4", "sdg4" -> 4. Angka >17 diabaikan (lihat parse).
_POLA_SDG = re.compile(r"\bsdgs?\s*[-:]?\s*(\d{1,2})\b")
_POLA_TAHUN = re.compile(r"\b(\d{4})\b")
_POLA_AKREDITASI = re.compile(r"\b(akreditasi|led|lkps)\b")
TAHUN_MIN, TAHUN_MAKS = 2000, 2030

# Kunci session_state (satu kali pakai: di-pop oleh halaman tujuan).
KUNCI_PILAR = "filter_pilar_awal"
KUNCI_TEMA = "filter_tema_awal"
KUNCI_SDG = "filter_sdg_awal"
KUNCI_TAHUN = "filter_tahun_awal"
KUNCI_PESAN = "pencarian_pesan"
# Kunci widget filter di sidebar (page_dampak.py / page_sdgs.py).
WIDGET_TAHUN = "f_tahun"
WIDGET_PILAR = "f_pilar"
WIDGET_SDG = "f_sdg"


@dataclass
class Hasil:
    query: str
    halaman: str = "dampak"
    pilar: list[str] = field(default_factory=list)
    tema: list[str] = field(default_factory=list)  # kunci LABEL_TOPIC
    sdg: list[int] = field(default_factory=list)
    tahun: tuple[str, str] | None = None
    cocok: bool = False  # False = tidak ada kata kunci yang dikenali


def _ada_kata(kata: str, teks: str) -> bool:
    """Cocokkan sebagai KATA UTUH, bukan potongan kata: tanpa ini "led"
    (dokumen akreditasi) ikut kena di "boleh"/"pemuliaan", dan "energi" kena
    di "sinergi"."""
    return re.search(rf"(?<!\w){re.escape(kata)}(?!\w)", teks) is not None


def parse(query: str) -> Hasil:
    """Terjemahkan query bebas jadi halaman tujuan + filter awal."""
    q = " ".join(query.lower().split())
    h = Hasil(query=query.strip())

    # 1) Akreditasi = prioritas utama, kata kunci lain diabaikan.
    if _POLA_AKREDITASI.search(q):
        h.halaman, h.cocok = "akreditasi", True
        return h

    # 2) SDG: nomor 1-17 saja. "sdg 2024" -> 2024 bukan SDG, tapi nanti
    #    tetap tertangkap sebagai TAHUN di langkah 4.
    h.sdg = sorted({n for n in (int(m) for m in _POLA_SDG.findall(q)) if 1 <= n <= 17})

    # 3) Pilar (dampak) langsung dari namanya.
    h.pilar = [p for p in PILAR if _ada_kata(p.lower(), q)]

    # 4) Tema Kepmen: nama resmi (LABEL_TOPIC) ATAU kamus kata kunci yang
    #    dipakai pipeline tagging (KEYWORDS_ALL) -- sumber yang sama.
    for kunci, label in LABEL_TOPIC.items():
        cocok = _ada_kata(label.lower(), q) or any(
            _ada_kata(kw.lower(), q) for kw in KEYWORDS_ALL.get(kunci, [])
        )
        if cocok:
            h.tema.append(kunci)
    # Tema menyiratkan pilarnya (mis. "panel surya" -> tema Energi ->
    # Lingkungan) supaya filter tema tidak tersembunyi karena pilarnya mati.
    for kunci in h.tema:
        p = TOPIK_KEPMEN_ALL[kunci]["dampak"]
        if p not in h.pilar:
            h.pilar.append(p)
    h.pilar = [p for p in PILAR if p in h.pilar]  # urutan tetap

    # 5) Tahun 4 digit dalam rentang wajar. Satu angka -> rentang 1 tahun,
    #    dua angka atau lebih -> dari yang terkecil ke terbesar.
    tahun = sorted({
        t for t in _POLA_TAHUN.findall(q) if TAHUN_MIN <= int(t) <= TAHUN_MAKS
    })
    if tahun:
        h.tahun = (tahun[0], tahun[-1])

    h.cocok = bool(h.sdg or h.pilar or h.tema or h.tahun)

    # 6) Routing.
    if h.sdg and (h.pilar or h.tema):
        h.halaman = "dampak-sdgs"
    elif h.sdg:
        h.halaman = "sdgs"
    else:
        h.halaman = "dampak"  # termasuk kasus "tidak cocok apa pun"
    return h


def ringkas(h: Hasil) -> str:
    """Kalimat penjelas: kenapa user mendarat di halaman ini dengan filter ini."""
    if not h.cocok:
        return (
            f'Tidak ditemukan kata kunci spesifik pada "{h.query}" — menampilkan '
            "Analisis Dampak secara umum. Gunakan filter di sidebar untuk "
            "mempersempit."
        )
    bagian = [f"**{NAMA_HALAMAN[h.halaman]}**"]
    if h.pilar:
        bagian.append("dampak " + ", ".join(h.pilar))
    if h.tema:
        bagian.append("tema " + ", ".join(LABEL_TOPIC[k] for k in h.tema))
    if h.sdg:
        bagian.append("SDG " + ", ".join(str(s) for s in h.sdg))
    if h.tahun:
        bagian.append(
            f"tahun {h.tahun[0]}" if h.tahun[0] == h.tahun[1]
            else f"tahun {h.tahun[0]}–{h.tahun[1]}"
        )
    teks = f'Hasil pencarian "{h.query}" → menampilkan: ' + ", ".join(bagian) + "."
    if h.sdg and h.halaman == "dampak-sdgs":
        # Halaman ini memang belum punya widget filter SDG (lihat page_dampak.py:
        # sdg_pilih dipatok 1-17), jadi SDG-nya sengaja TIDAK diklaim ikut terpasang.
        teks += (
            " Catatan: filter SDG belum tersedia di halaman ini — buka halaman "
            "**SDGs** kalau ingin menyaring per SDG."
        )
    return teks


def simpan_hasil(h: Hasil) -> None:
    """Titipkan hasil parsing ke session_state SEBELUM pindah halaman."""
    st.session_state[KUNCI_PILAR] = h.pilar
    st.session_state[KUNCI_TEMA] = h.tema
    st.session_state[KUNCI_SDG] = h.sdg
    st.session_state[KUNCI_TAHUN] = h.tahun
    st.session_state[KUNCI_PESAN] = ringkas(h)


def _batasi_tahun(tahun: tuple[str, str] | None, opsi: list[str]) -> tuple[str, str] | None:
    """Tahun hasil parsing dipotong ke tahun yang BENAR-BENAR ada datanya --
    select_slider menolak value di luar options-nya."""
    if not tahun or not opsi:
        return None
    ada = [t for t in opsi if tahun[0] <= t <= tahun[1]]
    return (ada[0], ada[-1]) if ada else None


def terapkan_filter_awal(tahun_opsi: list[str], *, punya_sdg: bool = False) -> None:
    """Pasang hasil pencarian sebagai NILAI AWAL widget filter sidebar.

    WAJIB dipanggil sebelum widget-nya dibuat (Streamlit melarang mengubah
    state widget setelah instansiasi). Nilainya di-pop: sekali pakai, jadi
    pilihan user setelah itu tidak akan ditimpa lagi saat halaman rerun.
    """
    pilar = st.session_state.pop(KUNCI_PILAR, None)
    tema = st.session_state.pop(KUNCI_TEMA, None)
    sdg = st.session_state.pop(KUNCI_SDG, None)
    tahun = st.session_state.pop(KUNCI_TAHUN, None)
    if pilar is None and tema is None and sdg is None and tahun is None:
        return  # halaman dibuka biasa, bukan dari hasil pencarian

    rentang = _batasi_tahun(tahun, tahun_opsi)
    if rentang:
        st.session_state[WIDGET_TAHUN] = rentang
    if pilar:
        st.session_state[WIDGET_PILAR] = pilar
        # Tema per pilar: hanya tema yang cocok, sisanya dibiarkan lengkap.
        for p in PILAR:
            tema_p = [k for k in (tema or []) if TOPIK_KEPMEN_ALL[k]["dampak"] == p]
            if tema_p:
                st.session_state[f"tema_pilar_{p}"] = tema_p
    if punya_sdg and sdg:
        st.session_state[WIDGET_SDG] = sdg


def banner() -> None:
    """Tampilkan sekali penjelasan hasil pencarian di halaman tujuan."""
    pesan = st.session_state.pop(KUNCI_PESAN, None)
    if pesan:
        st.info(f"🔍 {pesan}")
