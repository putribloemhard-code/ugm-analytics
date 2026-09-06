"""Halaman Akreditasi -- versi gabungan.

Dashboard kelengkapan data LED & LKPS (registry 49 item, form input manual,
generate dokumen Word) -- SATU sumber kebenaran dengan app akreditasi/ yang
berdiri sendiri (tabel MySQL sama). Ditambah Lampiran Data Dampak & SDG dari
analisis berita-dampak sendiri. Logikanya ada di page_akreditasi.render().
"""

import streamlit as st

from common import inject_css
from page_akreditasi import render

inject_css()

st.title("🎓 Akreditasi")
st.caption(
    "Kelengkapan data LED & LKPS (Prodi MEI, dua dokumen terpisah) + Lampiran Data Dampak & SDG "
    "dari berita-dampak. Isi form input manual di tiap item, lalu generate laporan Word."
)

render()
