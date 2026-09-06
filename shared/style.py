"""CSS global dipakai BARENG oleh semua dashboard (berita-dampak,
matkul-sustainability, akreditasi) -- SATU tempat untuk aturan struktural
Streamlit yang berlaku lintas proyek, supaya tidak ditempel ulang/didrift
per proyek.

Saat ini: penyamarataan tinggi kartu (st.metric / st.container(border=True) /
div custom lewat st.markdown) yang sejajar dalam satu baris st.columns --
kartu dengan teks lebih pendek tidak lagi tampak lebih pendek dari
tetangganya yang teksnya berbaris banyak. Solusinya CSS flexbox stretch
(RESPONSIF terhadap panjang teks yang bisa berubah-ubah tergantung data,
BUKAN angka tinggi tetap/hardcode).

Selector di bawah (stColumn, stVerticalBlock, dst.) diverifikasi langsung
lewat DOM Streamlit 1.61.1 (bukan ditebak) -- versi ini pakai `stColumn`,
BUKAN `column` seperti sebagian contoh CSS yang beredar untuk versi
Streamlit lebih lama; kalau versi Streamlit di-upgrade dan tinggi kartu
tiba-tiba tidak rata lagi, cek ulang nama data-testid via devtools sebelum
menambah selector baru di sini.

Pakai di tiap dashboard_*.py (root project masing-masing subproyek, satu
level di atas file ini):

    import sys
    from pathlib import Path
    sys.path.insert(0, str(Path(__file__).resolve().parents[1]))  # repo root
    from shared.style import apply_custom_css
    apply_custom_css()

Urutan panggilan terhadap CSS khusus proyek (mis. common.py punya
.pilar-card/.home-card sendiri) tidak masalah -- selector di sini generik
berbasis data-testid struktural Streamlit, tidak bentrok dengan class
custom proyek.
"""

import streamlit as st

CUSTOM_CSS = """
<style>
/* Kartu sejajar dalam satu baris st.columns rata tinggi ke kartu tertinggi.
   Rantai lengkap wajib di-stretch, bukan cuma elemen kolom terluar -- ada
   beberapa lapis wrapper Streamlit di antara stColumn dan elemen kartu yang
   sesungguhnya (st.metric, st.container(border=True), atau div custom lewat
   st.markdown). */
div[data-testid="stHorizontalBlock"] { align-items: stretch; }
div[data-testid="stColumn"] { display: flex; }
div[data-testid="stColumn"] > div { height: 100%; width: 100%; }
div[data-testid="stVerticalBlock"] { height: 100%; }
div[data-testid="stElementContainer"] { height: 100%; }

/* st.metric -- kartu background/border-nya sendiri (lihat CSS
   div[data-testid="stMetric"] di common.py tiap proyek) ikut memanjang
   penuh, bukan cuma area di sekitarnya. */
div[data-testid="stMetric"] { height: 100%; box-sizing: border-box; }

/* st.container(border=True) -- wrapper flex Streamlit utk container
   berbatas; belum ada pemakaian nyata di dashboard manapun saat modul ini
   ditulis, disertakan untuk jaga-jaga (belum diverifikasi visual dgn kasus
   nyata seperti dua pola di atas). */
div[data-testid="stLayoutWrapper"] { height: 100%; }
div[data-testid="stLayoutWrapper"] > div[data-testid="stVerticalBlock"] {
    display: flex; flex-direction: column; height: 100%; box-sizing: border-box;
}

/* div custom lewat st.markdown(unsafe_allow_html=True) (mis. .pilar-card,
   .home-card di berita-dampak/common.py) -- proyek yang mendefinisikan
   class kartu sendiri WAJIB tambah `height: 100%; box-sizing: border-box;`
   di definisi class itu supaya kartunya sendiri (bukan cuma wrapper-nya)
   ikut memanjang mengisi tinggi kolom yang sudah di-stretch di atas. */
</style>
"""


def apply_custom_css() -> None:
    st.markdown(CUSTOM_CSS, unsafe_allow_html=True)
